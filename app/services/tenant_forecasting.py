"""
Prophet tenant load forecasting service.

Implements real time-series forecasting using Meta's Prophet algorithm
trained on 3 years of historical hourly load observations (26,304 rows)
from the Monash/Zenodo public electricity dataset.
"""

from __future__ import annotations

import json
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import pandas as pd
from prophet import Prophet
from prophet.serialize import model_to_json, model_from_json
from sqlalchemy.orm import Session

from app.models import base as _register_all_models  # noqa: F401
from app.models.tenant import Tenant
from app.models.public_load import PublicLoadSeries, PublicLoadObservation
from app.schemas.forecasting import ForecastDataPoint, TenantForecastResponse

logger = logging.getLogger(__name__)

# List of the six selected series in cluster order
SELECTED_SERIES = ["T258", "T11", "T301", "T300", "T84", "T3"]

# Map profile types to series names
PROFILE_TO_SERIES = {
    "TEXTILE_MANUFACTURING": "T258",
    "FOOD_PROCESSING": "T11",
    "ELECTRONICS_MANUFACTURING": "T301",
    "PACKAGING_UNIT": "T300",
    "GENERAL_MANUFACTURING": "T84",
    "ENGINEERING_WORKSHOP": "T3",
}

# Directory where serialized Prophet models are stored
MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "resources", "models")


class TenantForecastingError(Exception):
    """Base exception for tenant forecasting service failures."""


def get_series_for_tenant(tenant_id: int, tenant: Optional[Tenant]) -> str:
    """Determine which public load series maps to the given tenant ID/profile."""
    if tenant and tenant.source_client_series_id:
        return tenant.source_client_series_id
    
    if tenant and tenant.profile_type:
        profile_val = tenant.profile_type.value if hasattr(tenant.profile_type, "value") else str(tenant.profile_type)
        if profile_val in PROFILE_TO_SERIES:
            return PROFILE_TO_SERIES[profile_val]

    # Deterministic fallback based on ID
    idx = (tenant_id - 1) % len(SELECTED_SERIES)
    return SELECTED_SERIES[idx]


def prepare_tenant_training_data(db: Session, series_name: str) -> pd.DataFrame:
    """
    Query historical observations for a series and return a DataFrame
    with normalized ['ds', 'y'] columns.
    """
    series = db.query(PublicLoadSeries).filter(PublicLoadSeries.series_name == series_name).first()
    if not series:
        raise TenantForecastingError(f"Public load series '{series_name}' not found in database.")

    # Query all observations
    records = (
        db.query(PublicLoadObservation.timestamp_local, PublicLoadObservation.hourly_average_kw)
        .filter(PublicLoadObservation.series_id == series.id)
        .order_by(PublicLoadObservation.timestamp_local.asc())
        .all()
    )

    if not records:
        raise TenantForecastingError(f"No observations found for series '{series_name}' (ID: {series.id})")

    # Normalize timestamps: round to exact hourly boundary during preprocessing
    data = []
    for ts_local, kw in records:
        # Parse timestamp to pandas Timestamp to enable rounding
        dt = pd.Timestamp(ts_local)
        
        # Exact hourly boundary normalization
        ds = dt.round("h")
        data.append({"ds": ds, "y": kw})

    df = pd.DataFrame(data)
    
    # Drop duplicates if any due to rounding (should be none based on audit)
    df = df.drop_duplicates(subset=["ds"])
    return df


def train_tenant_prophet_model(df: pd.DataFrame) -> Prophet:
    """
    Train a Prophet model on the load profile DataFrame.
    Uses growth='flat' to prevent runaway trend extrapolation over 12 years.
    Enables daily, weekly, and yearly seasonality since we have 3 years of data.
    """
    if len(df) < 24:
        raise TenantForecastingError(f"Insufficient training records: required >= 24, got {len(df)}")

    model = Prophet(
        growth="flat",
        daily_seasonality=True,
        weekly_seasonality=True,
        yearly_seasonality=True,
    )
    model.fit(df)
    return model


def get_model_path(series_name: str) -> str:
    """Get absolute path to serialized model JSON file."""
    return os.path.join(MODELS_DIR, f"{series_name}.json")


def load_model_from_cache(series_name: str) -> Optional[Prophet]:
    """Load serialized model from disk cache if it exists."""
    path = get_model_path(series_name)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                model_json = f.read()
            return model_from_json(model_json)
        except Exception as exc:
            logger.warning("Failed to deserialize model for %s from %s: %s", series_name, path, exc)
    return None


def save_model_to_cache(series_name: str, model: Prophet) -> None:
    """Serialize and save model to disk cache."""
    try:
        os.makedirs(MODELS_DIR, exist_ok=True)
        path = get_model_path(series_name)
        model_json = model_to_json(model)
        with open(path, "w", encoding="utf-8") as f:
            f.write(model_json)
        logger.info("Saved serialized Prophet model for %s to %s", series_name, path)
    except Exception as exc:
        logger.warning("Failed to serialize and save model for %s: %s", series_name, exc)


def generate_demo_tenant_forecast(
    tenant_id: int,
    tenant_name: str,
    hours: int,
    start_time: datetime,
) -> TenantForecastResponse:
    """Fallback generator that builds a simulated tenant load forecast (returns is_demo=True)."""
    data: List[ForecastDataPoint] = []
    total_kwh = 0.0
    peak_kw = 0.0

    load_factors = [
        0.30, 0.25, 0.25, 0.25, 0.30, 0.50,
        0.75, 0.90, 1.00, 0.98, 0.95, 0.90,
        0.80, 0.92, 0.95, 0.98, 0.90, 0.70,
        0.55, 0.45, 0.40, 0.35, 0.35, 0.30
    ]

    base_demand_kw = 150.0 + (tenant_id * 30.0 % 200.0)

    for i in range(hours):
        ts = start_time + timedelta(hours=i)
        hour_of_day = ts.hour
        factor = load_factors[hour_of_day % 24]
        pred = round(base_demand_kw * factor, 2)
        lower = round(pred * 0.90, 2)
        upper = round(pred * 1.10, 2)

        if pred > peak_kw:
            peak_kw = pred
        total_kwh += pred

        data.append(
            ForecastDataPoint(
                timestamp=ts.strftime("%Y-%m-%dT%H:00:00"),
                predicted_value_kw=pred,
                lower_bound_kw=lower,
                upper_bound_kw=upper,
            )
        )

    return TenantForecastResponse(
        tenant_id=tenant_id,
        tenant_name=tenant_name,
        forecast_period_hours=hours,
        forecast_data=data,
        total_consumption_forecast_kwh=round(total_kwh, 2),
        peak_demand_kw=round(peak_kw, 2),
        is_demo=True,
        explanatory_note="Prototype demo response — Prophet model training failed or missing data.",
    )


def generate_tenant_forecast(
    db: Session,
    tenant_id: int,
    hours: int = 24,
    start_time: Optional[datetime] = None,
) -> TenantForecastResponse:
    """
    Generate a real Prophet-based load forecast for a tenant.
    Loads serialized model from cache, or trains on-the-fly and saves to cache if missing.
    Ensures non-negative predictions. Falls back to demo forecast on failure.
    """
    tenant = db.get(Tenant, tenant_id)
    tenant_name = tenant.name if tenant else f"Tenant #{tenant_id}"
    series_name = get_series_for_tenant(tenant_id, tenant)

    if start_time is None:
        start_dt = datetime.now()
    else:
        start_dt = start_time

    start_dt = start_dt.replace(minute=0, second=0, microsecond=0)
    if start_dt.tzinfo:
        start_dt = start_dt.replace(tzinfo=None)

    try:
        # 1. Attempt to load model from cache
        model = load_model_from_cache(series_name)

        # 2. Train on-the-fly if cache miss
        if not model:
            logger.info("Cache miss for model %s. Training on-the-fly...", series_name)
            df = prepare_tenant_training_data(db, series_name)
            model = train_tenant_prophet_model(df)
            save_model_to_cache(series_name, model)

        # 3. Create future dataframe
        future = pd.DataFrame({"ds": [start_dt + timedelta(hours=i) for i in range(hours)]})
        forecast_raw = model.predict(future)

        # 4. Post-process predictions
        forecast_data: List[ForecastDataPoint] = []
        total_kwh = 0.0
        peak_kw = 0.0

        for _, row in forecast_raw.iterrows():
            ts_val: datetime = row["ds"]
            ts_str = ts_val.strftime("%Y-%m-%dT%H:00:00")

            # Non-negative clipping for physical demand consistency
            pred = round(max(0.0, float(row["yhat"])), 2)
            lower = round(max(0.0, float(row["yhat_lower"])), 2)
            upper = round(max(0.0, float(row["yhat_upper"])), 2)

            # Enforce mathematical bounds sanity
            if lower > pred:
                lower = pred
            if upper < pred:
                upper = pred

            if pred > peak_kw:
                peak_kw = pred
            total_kwh += pred

            forecast_data.append(
                ForecastDataPoint(
                    timestamp=ts_str,
                    predicted_value_kw=pred,
                    lower_bound_kw=lower,
                    upper_bound_kw=upper,
                )
            )

        # 5. Populate response with clear provenance metadata
        explanatory_note = (
            f"Prophet tenant load forecast trained on 26,304 hourly observations from the Monash/Zenodo "
            f"public electricity dataset. Series '{series_name}' serves as the historical shape archetype. "
            f"Predictions extrapolated with flat growth trend to preserve seasonal stability."
        )

        return TenantForecastResponse(
            tenant_id=tenant_id,
            tenant_name=tenant_name,
            forecast_period_hours=hours,
            forecast_data=forecast_data,
            total_consumption_forecast_kwh=round(total_kwh, 2),
            peak_demand_kw=round(peak_kw, 2),
            is_demo=False,
            explanatory_note=explanatory_note,
        )
    except Exception as exc:
        logger.warning(
            "Prophet tenant forecasting failed or missing data for series %s: %s. Falling back to demo forecast.",
            series_name,
            exc,
        )
        return generate_demo_tenant_forecast(tenant_id, tenant_name, hours, start_dt)
