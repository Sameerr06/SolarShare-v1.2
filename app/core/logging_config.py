"""
Application-wide logging configuration.

Phase 1 uses standard library logging with a consistent formatter across
the app. Later phases (ingestion, forecasting, optimization, billing) should
acquire loggers via `logging.getLogger(__name__)` and rely on this setup
rather than configuring logging themselves.
"""

import logging
import sys

from app.core.config import settings


def configure_logging() -> None:
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Avoid duplicate handlers if configure_logging() is called more than
    # once (e.g. during tests that create the app multiple times).
    if root_logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Quiet down noisy third-party loggers at INFO by default.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
