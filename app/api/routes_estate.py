"""
API routes for Estate and Location management correlated with NASA POWER
weather data.

Changing an estate's coordinates is the entry point for "give me data for where
I actually am": the coordinates live on the `Estate` row (never hardcoded in
ingestion code), `ingest_nasa_power_range` reads them straight off the estate,
and its cache key is a hash of (lat, lon, params, dates, ...) — so a new location
can never be served another location's cached response.

DATA-INTEGRITY NOTE: `WeatherObservation` and `SolarGenerationEstimate` are
keyed by (estate_id, timestamp) only. If an estate moves, previously-ingested
rows for that estate describe the OLD coordinates and would silently appear
alongside new-location rows in the same time series. `_purge_stale_location_rows`
removes exactly those rows (identified by their recorded provenance
latitude/longitude, which differ from the new ones) whenever the coordinates
actually change, so one estate never mixes two locations. Renaming an estate
does NOT purge anything.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.core.config import settings
from app.db.session import get_db
from app.models.config import PVConfig
from app.models.enums import UserRole
from app.models.estate import Estate
from app.models.weather import SolarGenerationEstimate, WeatherObservation
from app.schemas.estate import (
    PRESET_ESTATES,
    EstateCreate,
    EstatePreset,
    EstateRead,
    EstateSyncWeatherRequest,
    EstateSyncWeatherResponse,
    EstateUpdate,
)
from app.services.nasa_power_ingestion import NasaPowerIngestionError, ingest_nasa_power_range
from app.services.solar_generation import estimate_for_range

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/estates", tags=["estates"])

# Coordinates are compared with a tolerance: two values that differ only by
# floating-point noise must not be treated as a different location.
_COORD_EPSILON = 1e-6

# Default sync window when the caller doesn't specify dates. Kept small because
# each hour is one HTTP row ingested per estate.
_DEFAULT_SYNC_DAYS = 3
_MAX_SYNC_DAYS = 31


def _build_estate_read(db: Session, estate: Estate) -> EstateRead:
    return EstateRead(
        id=estate.id,
        name=estate.name,
        latitude=estate.latitude,
        longitude=estate.longitude,
        timezone=estate.timezone,
        created_at=getattr(estate, "created_at", None),
        updated_at=getattr(estate, "updated_at", None),
        weather_observation_count=(
            db.query(WeatherObservation)
            .filter(WeatherObservation.estate_id == estate.id)
            .count()
        ),
        solar_generation_estimate_count=(
            db.query(SolarGenerationEstimate)
            .filter(SolarGenerationEstimate.estate_id == estate.id)
            .count()
        ),
    )


def _coordinates_changed(old: Estate, new_lat: float, new_lon: float) -> bool:
    return (
        abs(old.latitude - new_lat) > _COORD_EPSILON
        or abs(old.longitude - new_lon) > _COORD_EPSILON
    )


def _purge_stale_location_rows(db: Session, estate: Estate, new_lat: float, new_lon: float) -> int:
    """
    Delete this estate's weather/generation rows that were recorded at
    coordinates other than (new_lat, new_lon). Returns the number of
    WeatherObservation rows removed.

    Generation rows are removed by joining through their weather observation, so
    no orphans are left behind (both tables have FKs to estates but not to each
    other's rows in a cascade-safe way at delete time).
    """
    stale_obs_ids = [
        row.id
        for row in (
            db.query(WeatherObservation.id)
            .filter(
                WeatherObservation.estate_id == estate.id,
                (
                    func.abs(WeatherObservation.latitude - new_lat) > _COORD_EPSILON
                )
                | (
                    func.abs(WeatherObservation.longitude - new_lon) > _COORD_EPSILON
                ),
            )
            .all()
        )
    ]
    if not stale_obs_ids:
        return 0

    removed_estimates = (
        db.query(SolarGenerationEstimate)
        .filter(SolarGenerationEstimate.weather_observation_id.in_(stale_obs_ids))
        .delete(synchronize_session=False)
    )
    db.query(WeatherObservation).filter(
        WeatherObservation.id.in_(stale_obs_ids)
    ).delete(synchronize_session=False)
    db.commit()

    logger.info(
        "Estate id=%s moved to (%.4f, %.4f): purged %d stale weather observations and %d generation estimates "
        "recorded at the previous coordinates.",
        estate.id, new_lat, new_lon, len(stale_obs_ids), removed_estimates,
    )
    return len(stale_obs_ids)


def _ensure_active_pv_config(db: Session, estate_id: int) -> PVConfig:
    """
    Return the estate's active PVConfig, creating a documented prototype default
    if none exists (same convention as app/services/solar_forecasting.py).
    """
    pv_config = (
        db.query(PVConfig)
        .filter(PVConfig.estate_id == estate_id, PVConfig.is_active == True)  # noqa: E712
        .order_by(PVConfig.effective_from.desc())
        .first()
    )
    if pv_config is not None:
        return pv_config

    pv_config = PVConfig(
        estate_id=estate_id,
        capacity_kw=500.0,
        efficiency=0.20,
        performance_ratio=0.80,
        effective_from=datetime.now(timezone.utc),
        is_active=True,
        notes=(
            "Prototype PV configuration assumption auto-created because no active "
            "PVConfig existed for this estate (500 kW STC capacity, 80% PR) — not an "
            "actual installed-equipment specification."
        ),
    )
    db.add(pv_config)
    db.commit()
    db.refresh(pv_config)
    logger.info("Auto-created prototype PVConfig id=%s for estate_id=%s", pv_config.id, estate_id)
    return pv_config


@router.get(
    "/presets",
    response_model=List[EstatePreset],
    dependencies=[Depends(get_current_user)],
)
def get_presets() -> List[EstatePreset]:
    """Ready-made locations the operator may switch to in one click."""
    return PRESET_ESTATES


@router.get(
    "",
    response_model=List[EstateRead],
    dependencies=[Depends(get_current_user)],
)
def list_estates(db: Session = Depends(get_db)) -> List[EstateRead]:
    estates = db.query(Estate).order_by(Estate.id).all()
    return [_build_estate_read(db, estate) for estate in estates]


@router.get(
    "/active",
    response_model=EstateRead,
    dependencies=[Depends(get_current_user)],
)
def get_active_estate(db: Session = Depends(get_db)) -> EstateRead:
    """
    The estate the dashboard uses when no explicit `estate_id` is supplied.

    `Estate` has no `is_active` column, so this is defined as the lowest-id
    estate — deterministic, and stable across restarts.
    """
    estate = db.query(Estate).order_by(Estate.id).first()
    if estate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No estate configured")
    return _build_estate_read(db, estate)


@router.get(
    "/{estate_id}",
    response_model=EstateRead,
    dependencies=[Depends(get_current_user)],
)
def get_estate_by_id(estate_id: int, db: Session = Depends(get_db)) -> EstateRead:
    estate = db.get(Estate, estate_id)
    if estate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estate not found")
    return _build_estate_read(db, estate)


@router.put(
    "/{estate_id}",
    response_model=EstateRead,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
def update_estate(
    estate_id: int,
    payload: EstateUpdate,
    db: Session = Depends(get_db),
) -> EstateRead:
    """
    Update an estate's name / coordinates / timezone.

    Changing the coordinates also discards that estate's previously-ingested
    weather + generation rows (see `_purge_stale_location_rows`) so the new
    location is fetched clean rather than blended with the old one. Call
    `POST /api/estates/{id}/sync-weather` afterwards to fetch data for the new
    coordinates.
    """
    estate = db.get(Estate, estate_id)
    if estate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estate not found")

    new_lat = payload.latitude if payload.latitude is not None else estate.latitude
    new_lon = payload.longitude if payload.longitude is not None else estate.longitude

    if _coordinates_changed(estate, new_lat, new_lon):
        _purge_stale_location_rows(db, estate, new_lat, new_lon)

    if payload.name is not None:
        estate.name = payload.name
    estate.latitude = new_lat
    estate.longitude = new_lon
    if payload.timezone is not None:
        estate.timezone = payload.timezone

    db.commit()
    db.refresh(estate)
    logger.info(
        "Estate id=%s updated: name=%r lat=%.4f lon=%.4f tz=%s",
        estate.id, estate.name, estate.latitude, estate.longitude, estate.timezone,
    )
    return _build_estate_read(db, estate)


@router.post(
    "",
    response_model=EstateRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
def create_estate(payload: EstateCreate, db: Session = Depends(get_db)) -> EstateRead:
    estate = Estate(
        name=payload.name,
        latitude=payload.latitude,
        longitude=payload.longitude,
        timezone=payload.timezone,
    )
    db.add(estate)
    db.commit()
    db.refresh(estate)
    logger.info("Created estate id=%s at (%.4f, %.4f)", estate.id, estate.latitude, estate.longitude)
    return _build_estate_read(db, estate)


@router.post(
    "/{estate_id}/sync-weather",
    response_model=EstateSyncWeatherResponse,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
def sync_estate_weather(
    estate_id: int,
    payload: Optional[EstateSyncWeatherRequest] = None,
    db: Session = Depends(get_db),
) -> EstateSyncWeatherResponse:
    """
    Fetch NASA POWER hourly weather for an estate's CURRENT coordinates and
    derive solar generation estimates from it.

    This is the step that makes "change coordinates → get data for them" work
    end to end: the estate's stored lat/lon are handed to the NASA POWER
    client, the response is validated and persisted with full provenance, and
    `estimate_for_range` turns each GHI reading into estimated kWh using the
    estate's active PVConfig.
    """
    estate = db.get(Estate, estate_id)
    if estate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estate not found")

    body = payload or EstateSyncWeatherRequest()

    # NASA POWER's hourly RE parameters lag real time by months, so "the last
    # few days" always comes back as fill values. Default the window into the
    # range the source can actually serve (see settings.nasa_power_data_lag_days)
    # while still honouring explicit dates from the caller.
    end_date = body.end_date or (date.today() - timedelta(days=settings.nasa_power_data_lag_days))
    start_date = body.start_date or (end_date - timedelta(days=_DEFAULT_SYNC_DAYS))
    if start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="start_date must not be after end_date",
        )
    if (end_date - start_date).days + 1 > _MAX_SYNC_DAYS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Date range too large — sync is limited to {_MAX_SYNC_DAYS} days per request.",
        )

    # Defensive: if the coordinates changed without a purge having run, clean up
    # so the response never blends two locations.
    stale_removed = 0
    stale_ids = [
        row.id
        for row in (
            db.query(WeatherObservation.id)
            .filter(
                WeatherObservation.estate_id == estate.id,
                (
                    func.abs(WeatherObservation.latitude - estate.latitude) > _COORD_EPSILON
                )
                | (
                    func.abs(WeatherObservation.longitude - estate.longitude) > _COORD_EPSILON
                ),
            )
            .all()
        )
    ]
    if stale_ids:
        db.query(SolarGenerationEstimate).filter(
            SolarGenerationEstimate.weather_observation_id.in_(stale_ids)
        ).delete(synchronize_session=False)
        stale_removed = (
            db.query(WeatherObservation)
            .filter(WeatherObservation.id.in_(stale_ids))
            .delete(synchronize_session=False)
        )
        db.commit()

    pv_config = _ensure_active_pv_config(db, estate.id)

    try:
        result = ingest_nasa_power_range(
            db=db,
            estate=estate,
            start_date=start_date,
            end_date=end_date,
            use_cache=body.use_cache,
        )
    except NasaPowerIngestionError as exc:
        logger.error("NASA POWER sync failed for estate_id=%s: %s", estate.id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    estimates_written = estimate_for_range(db, estate.id, pv_config)

    # Data-quality reporting: separate hours that actually carried a GHI reading
    # from hours NASA POWER has not processed yet (fill value -> NULL).
    with_ghi = (
        db.query(WeatherObservation)
        .filter(
            WeatherObservation.estate_id == estate.id,
            WeatherObservation.allsky_sfc_sw_dwn.isnot(None),
        )
        .count()
    )
    total_obs = (
        db.query(WeatherObservation)
        .filter(WeatherObservation.estate_id == estate.id)
        .count()
    )
    missing_ghi = max(total_obs - with_ghi, 0)

    warning = None
    if total_obs > 0 and with_ghi == 0:
        warning = (
            f"No irradiance readings available for {start_date}..{end_date} at "
            f"({estate.latitude}, {estate.longitude}). NASA POWER's hourly data lags "
            f"real time by roughly {settings.nasa_power_data_lag_days} days, so this "
            "window is probably too recent — try an earlier date range."
        )
    elif missing_ghi > 0:
        warning = (
            f"{missing_ghi} of {total_obs} hours have no irradiance reading "
            "(nighttime, or not yet processed by NASA POWER)."
        )

    return EstateSyncWeatherResponse(
        estate_id=estate.id,
        latitude=estate.latitude,
        longitude=estate.longitude,
        start_date=start_date,
        end_date=end_date,
        records_written=result.get("records_written", 0),
        generation_estimates_written=estimates_written,
        data_status=result.get("data_status", "UNKNOWN"),
        cache_hit=result.get("cache_hit", False),
        pv_config_id=pv_config.id,
        stale_rows_removed=stale_removed,
        message=(
            f"Fetched {result.get('records_written', 0)} hourly NASA POWER records for "
            f"({estate.latitude}, {estate.longitude}) and derived "
            f"{estimates_written} generation estimates."
        ),
        hours_with_ghi=with_ghi,
        hours_missing_ghi=missing_ghi,
        warning=warning,
    )