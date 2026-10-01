"""
NASA POWER ingestion orchestration.

Ties together app/integrations/nasa_power.py (HTTP + validation) with the
database: cache-first lookup, live fetch on cache miss, raw-response
caching, and persistence into `WeatherObservation` rows with full
provenance. Implements the fallback ladder from the locked specification
§16 (cache -> live -> [no silent demo-data substitution without explicit
opt-in, and never mislabeled as live]).
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.integrations.nasa_power import (
    NasaPowerError,
    NasaPowerRequestError,
    NasaPowerRequestParams,
    ParsedWeatherRecord,
    fetch_nasa_power,
    parse_and_validate_response,
)
from app.models.estate import Estate
from app.models.weather import NasaPowerCache, WeatherObservation

logger = logging.getLogger(__name__)


class NasaPowerIngestionError(Exception):
    """Raised when ingestion cannot produce trustworthy data by any path (cache or live)."""


def _get_cached_response(db: Session, cache_key: str) -> Optional[NasaPowerCache]:
    return db.query(NasaPowerCache).filter(NasaPowerCache.cache_key == cache_key).first()


def _store_cache(db: Session, params: NasaPowerRequestParams, raw: dict) -> NasaPowerCache:
    """
    Upsert by cache_key: if an identical request was already cached, its raw
    response is refreshed in place rather than raising a UNIQUE-constraint
    error. This matters because `use_cache=False` deliberately bypasses the
    *read* side of the cache (to force a live re-fetch) without meaning the
    cache should stop being written/maintained.
    """
    existing = _get_cached_response(db, params.cache_key())
    target = existing or NasaPowerCache(cache_key=params.cache_key())

    target.latitude = params.latitude
    target.longitude = params.longitude
    target.parameters = ",".join(params.parameters)
    target.start_date = params.start_date
    target.end_date = params.end_date
    target.community = params.community
    target.time_standard = params.time_standard
    target.raw_response_json = json.dumps(raw)
    target.retrieved_at = datetime.now(timezone.utc)

    if existing is None:
        db.add(target)
    db.commit()
    db.refresh(target)
    return target


def _persist_observations(
    db: Session,
    estate: Estate,
    params: NasaPowerRequestParams,
    records: List[ParsedWeatherRecord],
    retrieved_at: datetime,
    data_status: str,
) -> int:
    """
    Upsert-by-timestamp: existing rows for (estate, timestamp) are updated
    rather than duplicated, so re-running ingestion for an overlapping date
    range is safe. Returns the number of rows written (created or updated).
    """
    written = 0
    for record in records:
        existing = (
            db.query(WeatherObservation)
            .filter(WeatherObservation.estate_id == estate.id, WeatherObservation.timestamp == record.timestamp)
            .first()
        )
        target = existing or WeatherObservation(estate_id=estate.id, timestamp=record.timestamp)

        target.allsky_sfc_sw_dwn = record.values.get("ALLSKY_SFC_SW_DWN")
        target.t2m = record.values.get("T2M")
        target.rh2m = record.values.get("RH2M")
        target.ws10m = record.values.get("WS10M")
        target.source_name = "NASA POWER"
        target.source_type = "NASA_POWER"
        target.source_url = settings.nasa_power_base_url
        target.latitude = params.latitude
        target.longitude = params.longitude
        target.community = params.community
        target.parameters_requested = ",".join(params.parameters)
        target.time_standard = params.time_standard
        target.retrieved_at = retrieved_at
        target.data_status = data_status

        if existing is None:
            db.add(target)
        written += 1

    db.commit()
    return written


def ingest_nasa_power_range(
    db: Session,
    estate: Estate,
    start_date: date,
    end_date: date,
    parameters: Optional[List[str]] = None,
    use_cache: bool = True,
) -> dict:
    """
    Ingest NASA POWER hourly data for `estate` over [start_date, end_date]
    (inclusive), following the cache-first strategy from §15/§16.

    Returns a summary dict: {"records_written": int, "data_status": str,
    "cache_hit": bool}.

    Raises `NasaPowerIngestionError` if neither a valid cache entry nor a
    successful live fetch is available (no silent demo-data fallback here —
    per §16, demo fallback is an explicit, separately-invoked path, never
    an automatic substitution that could be mistaken for real data).
    """
    param_list = parameters or settings.nasa_power_parameters_list
    request_params = NasaPowerRequestParams(
        latitude=estate.latitude,
        longitude=estate.longitude,
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
        parameters=param_list,
    )
    cache_key = request_params.cache_key()

    raw_response = None
    data_status = "LIVE"
    cache_hit = False

    if use_cache:
        cached = _get_cached_response(db, cache_key)
        if cached is not None:
            logger.info("NASA POWER cache hit for key=%s", cache_key)
            raw_response = json.loads(cached.raw_response_json)
            data_status = "CACHED"
            cache_hit = True

    if raw_response is None:
        try:
            raw_response = fetch_nasa_power(request_params)
        except NasaPowerRequestError as exc:
            # Fallback ladder step 1: try cache even if use_cache was False,
            # since a live failure means cache (if any) is better than nothing.
            cached = _get_cached_response(db, cache_key)
            if cached is not None:
                logger.warning("NASA POWER live fetch failed (%s); falling back to cache.", exc)
                raw_response = json.loads(cached.raw_response_json)
                data_status = "CACHED"
                cache_hit = True
            else:
                raise NasaPowerIngestionError(
                    f"NASA POWER live fetch failed and no cached data is available for this request: {exc}"
                ) from exc
        else:
            _store_cache(db, request_params, raw_response)

    try:
        records = parse_and_validate_response(raw_response, expected_parameters=param_list)
    except NasaPowerError as exc:
        raise NasaPowerIngestionError(f"NASA POWER response failed validation: {exc}") from exc

    retrieved_at = datetime.now(timezone.utc)
    written = _persist_observations(db, estate, request_params, records, retrieved_at, data_status)

    logger.info(
        "NASA POWER ingestion complete: estate_id=%s range=%s..%s records_written=%s status=%s cache_hit=%s",
        estate.id, start_date, end_date, written, data_status, cache_hit,
    )
    return {"records_written": written, "data_status": data_status, "cache_hit": cache_hit}
