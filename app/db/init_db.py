"""
Database initialization strategy.

Phase 1 decision: use SQLAlchemy's `Base.metadata.create_all()` for schema
creation rather than Alembic migrations. This is a deliberate, documented
choice for the foundational phase:

- It keeps Phase 1 focused on structure/auth rather than migration tooling.
- It is sufficient for the SQLite local-development/demo target.
- It is NOT sufficient for iterative production schema evolution.

Recommendation for a later phase: introduce Alembic once the schema starts
evolving after data exists in a shared environment (i.e. once ingestion,
forecasting, allocation, or billing tables are added and need versioned
migrations rather than a fresh `create_all`). This module is intentionally
the single place that decision would be swapped in, so no other code
depends on *how* tables get created.
"""

import logging

# Importing the models module ensures every ORM model is registered on
# `Base.metadata` before `create_all()` is called. Without this import,
# SQLAlchemy would not know about tables defined in app/models/*.py.
from app.models import base  # noqa: F401
from app.db.session import Base, engine

logger = logging.getLogger(__name__)


def init_db() -> None:
    """Create all tables that don't already exist."""
    logger.info("Initializing database schema (create_all)...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database schema initialized.")
