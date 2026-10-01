"""
Pre-training and serialization script for all 6 selected tenant load profiles.

Trains Prophet models on the full 26,304 hourly observations for each series
and serializes them to JSON files under app/resources/models/.
"""

import os
import sys
import logging
import time

# Ensure workspace root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.logging_config import configure_logging
from app.db.session import SessionLocal
from app.services.tenant_forecasting import (
    SELECTED_SERIES,
    prepare_tenant_training_data,
    train_tenant_prophet_model,
    save_model_to_cache,
)

configure_logging()
logger = logging.getLogger(__name__)


def train_all_models() -> None:
    db = SessionLocal()
    try:
        logger.info("Starting Prophet pre-training workflow for %d selected series...", len(SELECTED_SERIES))
        start_total = time.time()
        
        for series_name in SELECTED_SERIES:
            logger.info("-------------------------------------------------------------")
            logger.info("Processing series: %s", series_name)
            start_single = time.time()
            
            try:
                # 1. Prepare data (including exact hour boundary normalization)
                df = prepare_tenant_training_data(db, series_name)
                logger.info("Loaded %d rows for series %s", len(df), series_name)
                
                # 2. Train model
                logger.info("Training Prophet model (daily, weekly, yearly seasonality, flat growth)...")
                model = train_tenant_prophet_model(df)
                
                # 3. Serialize and save to cache
                save_model_to_cache(series_name, model)
                
                elapsed = time.time() - start_single
                logger.info("Successfully trained and saved series %s in %.2fs", series_name, elapsed)
            except Exception as exc:
                logger.error("Failed to process series %s: %s", series_name, exc, exc_info=True)
                
        total_elapsed = time.time() - start_total
        logger.info("-------------------------------------------------------------")
        logger.info("Prophet pre-training workflow complete! Total time: %.2fs", total_elapsed)
    finally:
        db.close()


if __name__ == "__main__":
    train_all_models()
