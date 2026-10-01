"""
Custom SQLAlchemy column types.

SQLite (Phase 1/2's default database) does not natively preserve timezone
information on `DateTime` columns — values come back naive after a
round-trip, even when the column is declared `DateTime(timezone=True)`.
Since the locked specification requires UTC to be the single canonical
internal timestamp representation (§5: "Maintain one consistent canonical
timestamp representation internally"), `UTCDateTime` enforces that
contract explicitly: it requires timezone-aware UTC datetimes on write,
strips the tzinfo only for SQLite storage, and re-attaches UTC on read —
so application code always sees a timezone-aware UTC datetime regardless
of which backend (SQLite now, PostgreSQL later) is in use.
"""

from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator):
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError(
                f"UTCDateTime received a naive datetime ({value!r}); all timestamps must be "
                f"explicitly timezone-aware (UTC) before being persisted."
            )
        return value.astimezone(timezone.utc)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if value.tzinfo is None:
            # SQLite returns naive datetimes; since we only ever store UTC
            # (enforced in process_bind_param above), it's safe to re-attach.
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
