"""
Prophet solar PV generation forecasting service.

Implements real time-series forecasting using Meta's Prophet algorithm
trained on historical Model B PV generation estimates derived from real NASA POWER
weather observations.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone, tzinfo
from typing import List, Optional
from zoneinfo import ZoneInfo

import pandas as pd
from prophet import Prophet
from sqlalchemy.orm import Session

from app.models.config import PVConfig
from app.models.estate import Estate
from app.models.weather import SolarGenerationEstimate, WeatherObservation
from app.schemas.forecasting import ForecastDataPoint, SolarForecastResponse
from app.services.nasa_power_ingestion import ingest_nasa_power_range
from app.services.solar_generation import estimate_for_range

logger = logging.getLogger(__name__)


class SolarForecastingError(Exception):
    """Base exception for solar forecasting service failures."""


def resolve_display_timezone(db: Session, estate_id: int) -> tzinfo:
    """
    Timezone used to render forecast timestamps.

    Training data (NASA POWER) is stored in UTC (see WeatherObservation.timestamp),
    but charts are read as wall-clock time in the estate's own timezone, so the
    forecast points are converted before they leave the API.
    """
    estate = db.get(Estate, estate_id)
    tz_name = getattr(estate, "timezone", None) if estate is not None else None
    if tz_name:
        try:
            return ZoneInfo(tz_name)
        except Exception as exc:  # unknown tz name / missing tzdata
            logger.warning("Estate %s has unusable timezone %r: %s", estate_id, tz_name, exc)
    return datetime.now().astimezone().tzinfo or timezone.utc


def prepare_training_data(
    db: Session,
    estate_id: int = 1,
) -> pd.DataFrame:
    """
    Query historical solar generation estimates for an estate and format as
    a Prophet training DataFrame with columns ['ds', 'y'].
    
    If no SolarGenerationEstimate records exist in DB, attempts auto-computation
    from existing WeatherObservation records, or ingests default historical
    NASA POWER data for the estate.
    """
    records = (
        db.query(SolarGenerationEstimate)
        .filter(SolarGenerationEstimate.estate_id == estate_id)
        .order_by(SolarGenerationEstimate.timestamp.asc())
        .all()
    )

    if not records:
        # Step A: Check if WeatherObservations exist and calculate estimates
        obs_count = (
            db.query(WeatherObservation)
            .filter(WeatherObservation.estate_id == estate_id)
            .count()
        )
        if obs_count > 0:
            pv_config = (
                db.query(PVConfig)
                .filter(PVConfig.estate_id == estate_id, PVConfig.is_active == True)
                .order_by(PVConfig.effective_from.desc())
                .first()
            )
            if not pv_config:
                pv_config = PVConfig(
                    estate_id=estate_id,
                    capacity_kw=500.0,
                    efficiency=0.20,
                    performance_ratio=0.80,
                    effective_from=datetime.now(timezone.utc),
                    is_active=True,
                )
                db.add(pv_config)
                db.commit()
                db.refresh(pv_config)

            written = estimate_for_range(db, estate_id, pv_config)
            logger.info("Auto-computed %d SolarGenerationEstimate records from existing WeatherObservation rows", written)

            records = (
                db.query(SolarGenerationEstimate)
                .filter(SolarGenerationEstimate.estate_id == estate_id)
                .order_by(SolarGenerationEstimate.timestamp.asc())
                .all()
            )

    if not records:
        # Step B: Auto-ingest 2024 NASA POWER weather data for estate if offline ingestion hasn't run
        estate = db.get(Estate, estate_id)
        if estate:
            pv_config = (
                db.query(PVConfig)
                .filter(PVConfig.estate_id == estate_id, PVConfig.is_active == True)
                .order_by(PVConfig.effective_from.desc())
                .first()
            )
            if not pv_config:
                pv_config = PVConfig(
                    estate_id=estate_id,
                    capacity_kw=500.0,
                    efficiency=0.20,
                    performance_ratio=0.80,
                    effective_from=datetime.now(timezone.utc),
                    is_active=True,
                )
                db.add(pv_config)
                db.commit()
                db.refresh(pv_config)
            try:
                ingest_nasa_power_range(db, estate, date(2024, 1, 1), date(2024, 12, 31))
                estimate_for_range(db, estate_id, pv_config)
                records = (
                    db.query(SolarGenerationEstimate)
                    .filter(SolarGenerationEstimate.estate_id == estate_id)
                    .order_by(SolarGenerationEstimate.timestamp.asc())
                    .all()
                )
            except Exception as exc:
                logger.warning("Attempt to auto-ingest NASA POWER weather data failed: %s", exc)

    if not records:
        raise SolarForecastingError(f"No historical solar generation estimates found or computable for estate_id={estate_id}")

    data = []
    for r in records:
        ts = r.timestamp.replace(tzinfo=None) if r.timestamp.tzinfo else r.timestamp
        data.append({"ds": ts, "y": r.estimated_kwh})

    df = pd.DataFrame(data)
    return df


def train_prophet_model(df: pd.DataFrame) -> Prophet:
    """
    Train a Prophet model on the historical solar generation DataFrame.

    - ``growth='flat'``: PV output has no long-term trend, and a linear trend
      extrapolated past the last training record (the forecast window can sit
      months beyond it) either explodes to impossible kW values or collapses
      below zero.
    - ``daily_seasonality=True``: the hourly solar shape is always identifiable
      from >= 24 hourly records.
    - ``weekly_seasonality`` only with >= 14 days of history; with a handful of
      days the weekly terms alias the daily shape and distort the curve.
    - yearly seasonality stays off (the datasets here are too short to identify it).
    """
    if len(df) < 24:
        raise SolarForecastingError(f"Insufficient training records: required >= 24, got {len(df)}")

    model = Prophet(
        growth="flat",
        daily_seasonality=True,
        weekly_seasonality=len(df) >= 14 * 24,
        yearly_seasonality=False,
    )
    model.fit(df)
    return model


def generate_solar_forecast(
    db: Session,
    estate_id: int = 1,
    hours: int = 24,
    start_time: Optional[datetime] = None,
) -> SolarForecastResponse:
    """
    Generate a real Prophet-based solar PV generation forecast for the specified horizon.
    The forecast window starts at the current hour (not at the end of the training
    history) and every timestamp is returned in the estate's local timezone.
    Post-processes predictions and uncertainty bounds to guarantee non-negative solar generation.
    Returns a fully populated SolarForecastResponse with is_demo=False and complete provenance metadata.
    """
    tz = resolve_display_timezone(db, estate_id)

    try:
        df = prepare_training_data(db, estate_id=estate_id)
        model = train_prophet_model(df)
    except Exception as exc:
        # logger.exception (not warning) so the full traceback reaches the
        # operator: a silent fallback to a bell curve is a production incident,
        # not an informational event.
        logger.exception(
            "Prophet solar model unavailable for estate_id=%s — falling back to the "
            "DEMO curve. The response returned to the client is flagged is_demo=True "
            "with fallback_reason set; it is NOT a model output.",
            estate_id,
        )
        return _fallback_demo_forecast(estate_id, hours, f"{type(exc).__name__}: {exc}", tz=tz)

    min_ts = df["ds"].min()
    max_ts = df["ds"].max()
    rec_count = len(df)

    # Predict on a naive-UTC axis (the basis of the NASA POWER training rows),
    # starting at the current hour so a "24h horizon" really covers the next 24h.
    if start_time is None:
        start_utc = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    elif start_time.tzinfo is not None:
        start_utc = start_time.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
    else:
        # Naive callers pass estate-local wall clock, same basis as the output.
        start_utc = (
            start_time.replace(tzinfo=tz).astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)
        )
    start_naive = start_utc.replace(tzinfo=None)
    future = pd.DataFrame({"ds": [start_naive + timedelta(hours=i) for i in range(hours)]})

    forecast_raw = model.predict(future)

    forecast_data: List[ForecastDataPoint] = []
    total_kwh = 0.0
    peak_kw = 0.0

    for _, row in forecast_raw.iterrows():
        ts_val: datetime = row["ds"]
        # Model works in UTC; charts are read in the estate's timezone.
        ts_str = ts_val.replace(tzinfo=timezone.utc).astimezone(tz).isoformat(timespec="seconds")

        # Post-processing: non-negative clipping for physical solar generation (Requirements 8 & 9)
        pred = round(max(0.0, float(row["yhat"])), 2)
        lower = round(max(0.0, float(row["yhat_lower"])), 2)
        upper = round(max(0.0, float(row["yhat_upper"])), 2)

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

    now_utc_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return SolarForecastResponse(
        estate_id=estate_id,
        forecast_period_hours=hours,
        forecast_data=forecast_data,
        total_generation_forecast_kwh=round(total_kwh, 2),
        peak_generation_kw=round(peak_kw, 2),
        is_demo=False,
        explanatory_note=(
            f"Prophet solar PV generation forecast trained on {rec_count:,} hourly "
            f"Model B PV generation estimates derived from NASA POWER weather observations ({min_ts.strftime('%Y-%m-%d')} to {max_ts.strftime('%Y-%m-%d')})."
            f" Timestamps are in {getattr(tz, 'key', None) or tz}."
        ),
        model_name="Prophet",
        training_record_count=rec_count,
        training_start_date=min_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        training_end_date=max_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        generated_at=now_utc_str,
    )


def _fallback_demo_forecast(
    estate_id: int,
    hours: int,
    reason: str,
    tz: Optional[tzinfo] = None,
) -> SolarForecastResponse:
    tz = tz or datetime.now().astimezone().tzinfo or timezone.utc
    now = datetime.now(tz).replace(minute=0, second=0, microsecond=0)
    data: List[ForecastDataPoint] = []
    total_kwh = 0.0
    peak_kw = 0.0

    solar_factors = [
        0, 0, 0, 0, 0, 0,
        0.05, 0.20, 0.45, 0.70, 0.88, 0.96,
        1.00, 0.95, 0.85, 0.65, 0.38, 0.15,
        0.02, 0, 0, 0, 0, 0,
    ]

    for i in range(hours):
        ts = now + timedelta(hours=i)
        factor = solar_factors[ts.hour % 24]
        pred = round(380.0 * factor, 2)
        lower = round(max(0.0, pred * 0.85), 2)
        upper = round(pred * 1.15, 2)

        if pred > peak_kw:
            peak_kw = pred
        total_kwh += pred

        data.append(
            ForecastDataPoint(
                timestamp=ts.isoformat(timespec="seconds"),
                predicted_value_kw=pred,
                lower_bound_kw=lower,
                upper_bound_kw=upper,
            )
        )

    return SolarForecastResponse(
        estate_id=estate_id,
        forecast_period_hours=hours,
        forecast_data=data,
        total_generation_forecast_kwh=round(total_kwh, 2),
        peak_generation_kw=peak_kw,
        is_demo=True,
        explanatory_note=(
            "FALLBACK DEMO CURVE — NOT A MODEL OUTPUT. The Prophet solar model could "
            f"not be produced: {reason}. No solar forecast was actually computed for "
            "this request."
        ),
        model_name="Prophet (Demo Fallback)",
        training_record_count=0,
        training_start_date=None,
        training_end_date=None,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        fallback_reason=reason,
    )
