"""
SQLAlchemy engine and session management.

Phase 1 targets SQLite by default (per the locked specification: "SQLite may
be supported for easy local demonstration"), with `DATABASE_URL` making a
future move to PostgreSQL a configuration change, not a code change.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


def _normalize_database_url(url: str) -> str:
    """Make a plain Postgres URL usable by SQLAlchemy + the psycopg 3 driver.

    Hosted Postgres providers (Vercel marketplace integrations, Neon, Supabase,
    Railway...) hand out ``postgres://`` / ``postgresql://`` connection strings.
    SQLAlchemy would route those to psycopg2, which this project does not
    install, so rewrite the scheme to the psycopg 3 driver it does install.
    """
    if url.startswith("postgres://") or url.startswith("postgresql://"):
        _, _, rest = url.partition("://")
        return f"postgresql+psycopg://{rest}"
    return url


def _postgres_connect_args(url: str) -> dict:
    """Driver options for a transaction-pooling endpoint.

    Neon's *pooled* endpoint sits behind a proxy that multiplexes connections
    per transaction and cannot serve protocol-level prepared statements. psycopg
    3 exposes this as ``prepare_threshold=None`` (never prepare); the older
    ``pgbouncer=true`` conninfo option only exists on the asyncio driver.
    """
    if "-pooler" in url:
        return {"prepare_threshold": None}
    return {}


def _make_engine():
    connect_args = {}
    engine_kwargs = {"future": True}
    if settings.is_sqlite:
        # Needed for SQLite when used with FastAPI's threaded request handling.
        connect_args = {"check_same_thread": False}
    else:
        # Remote database (PostgreSQL on Vercel/Neon): connections sit idle in
        # the pool between requests and can be closed server-side, so validate
        # them on checkout and recycle them well before the server's idle
        # timeout instead of surfacing "server closed the connection" 500s.
        engine_kwargs.update(pool_pre_ping=True, pool_recycle=1800)
        connect_args.update(_postgres_connect_args(settings.database_url))
    return create_engine(
        _normalize_database_url(settings.database_url),
        connect_args=connect_args,
        **engine_kwargs,
    )


engine = _make_engine()

if settings.is_sqlite:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        """
        WAL journal mode + synchronous=NORMAL, applied to every new SQLite
        connection.

        Justification (bulk-ingestion scalability review): WAL mode allows
        writers and readers to proceed concurrently and is generally faster
        for write-heavy workloads than SQLite's default rollback-journal
        mode, while remaining fully crash-safe/durable — this is not a
        durability tradeoff. `synchronous=NORMAL` under WAL is a
        well-established, safe configuration: it remains durable against
        application crashes; the only residual risk is data loss on an
        OS-level power failure in the narrow window between a WAL commit
        and its checkpoint, which is an accepted, reversible tradeoff for
        this hackathon prototype. `synchronous=OFF` was deliberately NOT
        used, since it sacrifices meaningful durability guarantees for no
        real benefit here (the bulk-ingestion bottleneck this pragma
        change supports was Python/ORM-level overhead, not disk fsync
        frequency -- see app/services/electricity_ingestion.py).
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def get_db():
    """FastAPI dependency that yields a database session and ensures it's closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
