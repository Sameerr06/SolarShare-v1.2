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


def _make_engine():
    connect_args = {}
    if settings.is_sqlite:
        # Needed for SQLite when used with FastAPI's threaded request handling.
        connect_args = {"check_same_thread": False}
    return create_engine(settings.database_url, connect_args=connect_args, future=True)


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
