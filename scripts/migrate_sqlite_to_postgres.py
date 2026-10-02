"""
Migrate a local SQLite ``solarshare.db`` into PostgreSQL (Neon on Vercel).

Why this exists: the production database cannot be SQLite on Vercel (the
filesystem is read-only and ephemeral), so the ingested 8.4M-row dataset has to
be copied once into PostgreSQL. The schema is created by
``Base.metadata.create_all`` — the exact same code path the app runs at startup
(``app/db/init_db.py``) — so the target schema can never drift from the models.

Properties:
  * Idempotent/resumable — every INSERT is ``ON CONFLICT DO NOTHING`` on the
    primary key, so a crashed run can simply be restarted.
  * Streaming — the source is read with ``fetchmany`` batches; 8.4M rows never
    sit in memory at once.
  * Correct sequences — PostgreSQL SERIAL/IDENTITY sequences are advanced to
    ``max(id)`` afterwards, otherwise the first row the app inserts post-migration
    would collide with a migrated id.

Usage:
    python scripts/migrate_sqlite_to_postgres.py \
        --target "postgresql+psycopg://user:pass@host/db?sslmode=require" \
        [--source ./solarshare.db] [--batch 2000] [--drop] [--tables tenants,users]

Run it from the project root (the ``app`` package must be importable).
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from typing import Dict, Iterable, List, Sequence, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import Boolean, Integer, Table, create_engine
from sqlalchemy.types import TypeDecorator, TypeEngine

from app.db.session import Base
from app.models import base as _register_all_models  # noqa: F401  (registers every model)

MAX_PARAMS = 60_000  # Postgres protocol caps a statement at 65535 bind params


def _unwrap(col_type: TypeEngine) -> TypeEngine:
    return col_type.impl if isinstance(col_type, TypeDecorator) else col_type


def _adapt(value, col_type: TypeEngine):
    """Coerce a raw SQLite value into something psycopg can bind."""
    if value is None:
        return None
    base = _unwrap(col_type)
    if isinstance(base, Boolean):
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "t", "yes")
        return bool(value)
    if isinstance(base, Integer):
        return int(value)
    if isinstance(value, (bytes, bytearray)):
        return bytes(value).decode("utf-8")
    return value  # str (datetime/time/enum/text), float, pass-through


def _source_columns(conn: sqlite3.Connection, table_name: str) -> List[str]:
    return [row[1] for row in conn.execute(f'PRAGMA table_info("{table_name}")')]


def _insert_sql(table: Table, cols: Sequence[str]) -> str:
    """Single-row INSERT; rows are batched through DBAPI executemany (psycopg3
    implements that with pipeline mode, so it is effectively a bulk load)."""
    col_list = ", ".join(f'"{c}"' for c in cols)
    placeholders = ", ".join(["%s"] * len(cols))
    return (
        f'INSERT INTO "{table.name}" ({col_list}) VALUES ({placeholders}) '
        f"ON CONFLICT DO NOTHING"
    )


def migrate_table(
    src: sqlite3.Connection,
    target,
    table: Table,
    batch_size: int,
    where: str | None = None,
) -> Tuple[int, int]:
    src_cols = _source_columns(src, table.name)
    model_cols = [c.name for c in table.columns]
    missing = [c for c in model_cols if c not in src_cols]
    if missing:
        print(f"  ! {table.name}: model columns absent in source, inserted as NULL: {missing}")

    cols = [c for c in model_cols if c in src_cols]
    if not cols:
        print(f"  - {table.name}: skipped (no shared columns)")
        return 0, 0

    col_types = {c.name: c.type for c in table.columns}
    rows_per_stmt = max(1, min(batch_size, MAX_PARAMS // len(cols)))
    sql = _insert_sql(table, cols)
    where_sql = f" WHERE {where}" if where else ""

    cur = src.execute(
        f'SELECT {", ".join(chr(34) + c + chr(34) for c in cols)} FROM "{table.name}"{where_sql}'
    )
    total = 0
    with target.begin() as conn:
        while True:
            rows = cur.fetchmany(rows_per_stmt)
            if not rows:
                break
            batch: List[Tuple[object, ...]] = [
                tuple(_adapt(value, col_types[name]) for name, value in zip(cols, row))
                for row in rows
            ]
            conn.exec_driver_sql(sql, batch)  # executemany: pipeline mode in psycopg3
            total += len(batch)
        target_count = int(
            conn.exec_driver_sql(f'SELECT count(*) FROM "{table.name}"').scalar() or 0
        )
    return total, target_count


def advance_sequences(target, tables: Iterable[Table]) -> None:
    with target.begin() as conn:
        for table in tables:
            pk = list(table.primary_key.columns)
            if len(pk) != 1 or not isinstance(_unwrap(pk[0].type), Integer):
                continue
            seq = conn.exec_driver_sql(
                "SELECT pg_get_serial_sequence(%s, %s)", (table.name, pk[0].name)
            ).scalar()
            if not seq:
                continue
            max_id = conn.exec_driver_sql(f'SELECT max("{pk[0].name}") FROM "{table.name}"').scalar()
            if max_id is None:
                conn.exec_driver_sql("SELECT setval(%s, 1, false)", (seq,)).scalar()
            else:
                conn.exec_driver_sql("SELECT setval(%s, %s)", (seq, int(max_id))).scalar()
            print(f"  sequence {seq} -> {max_id or 'reset'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--target", default=os.environ.get("MIGRATE_DATABASE_URL") or os.environ.get("DATABASE_URL"),
                        help="PostgreSQL SQLAlchemy URL (or set MIGRATE_DATABASE_URL/DATABASE_URL)")
    parser.add_argument("--source", default="./solarshare.db", help="Source SQLite file")
    parser.add_argument("--batch", type=int, default=2000, help="Rows per INSERT statement")
    parser.add_argument("--tables", help="Comma-separated subset of tables (default: all)")
    parser.add_argument("--drop", action="store_true", help="Drop existing target tables first")
    parser.add_argument(
        "--selected-only",
        action="store_true",
        help=(
            "Only migrate hourly observations for the series selected by the load "
            "profiling step (public_load_series_profiles.is_selected). Every other "
            "table is migrated in full. Use it when the target has a storage cap "
            "smaller than the full 8.4M-row dataset (e.g. Neon's 0.5 GB free tier)."
        ),
    )
    parser.add_argument("--no-sequences", action="store_true",
                        help="Skip advancing Postgres sequences to max(id)")
    args = parser.parse_args()

    if not args.target or not args.target.startswith(("postgres", "postgresql")):
        print("error: --target must be a postgresql:// URL", file=sys.stderr)
        return 2
    if not os.path.exists(args.source):
        print(f"error: source database not found: {args.source}", file=sys.stderr)
        return 2

    tables: List[Table] = list(Base.metadata.sorted_tables)  # topological: FK parents first
    if args.tables:
        wanted = {t.strip() for t in args.tables.split(",") if t.strip()}
        unknown = wanted - {t.name for t in tables}
        if unknown:
            print(f"error: unknown tables: {sorted(unknown)}", file=sys.stderr)
            return 2
        tables = [t for t in tables if t.name in wanted]

    target = create_engine(args.target, pool_pre_ping=True, future=True)
    src = sqlite3.connect(f"file:{args.source}?mode=ro", uri=True)

    print(f"source: {args.source} ({os.path.getsize(args.source) / 1e6:.0f} MB)")
    print(f"target: {target.url.render_as_string(hide_password=True)}")
    print(f"tables: {', '.join(t.name for t in tables)}")

    # Session TZ matters: naive UTC strings read from SQLite must be stored as
    # the same instants in timestamptz columns.
    with target.begin() as conn:
        conn.exec_driver_sql("SET TIME ZONE 'UTC'")

    if args.drop:
        print("dropping target tables ...")
        Base.metadata.drop_all(bind=target)
    print("creating schema (Base.metadata.create_all) ...")
    Base.metadata.create_all(bind=target)

    failures = []
    started = time.time()
    for table in tables:
        t0 = time.time()
        where = None
        if args.selected_only and table.name == "public_load_observations":
            selected = [
                r[0]
                for r in src.execute(
                    "SELECT series_id FROM public_load_series_profiles WHERE is_selected = 1"
                )
            ]
            if not selected:
                print("  ! no selected series found - migrating every observation row")
            else:
                where = f"series_id IN ({', '.join(str(int(s)) for s in selected)})"
        inserted, target_count = migrate_table(src, target, table, args.batch, where)
        scope = "filtered" if where else "full"
        print(f"  {table.name:32s} {inserted:>10,} rows [{scope}]  ({time.time() - t0:5.1f}s)")
        src_count = src.execute(
            f'SELECT count(*) FROM "{table.name}"' + (f" WHERE {where}" if where else "")
        ).fetchone()[0]
        if target_count < src_count:
            failures.append((table.name, src_count, target_count))

    if not args.no_sequences and not args.tables:
        print("advancing sequences ...")
        advance_sequences(target, Base.metadata.sorted_tables)

    elapsed = time.time() - started
    print(f"\ndone in {elapsed/60:.1f} min")
    if failures:
        print("COUNT MISMATCHES (source -> target):")
        for name, s, t in failures:
            print(f"  {name}: {s:,} -> {t:,}")
        return 1
    print("all table counts match the source database")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
