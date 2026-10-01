"""
NASA POWER Hourly Point API integration.

============================================================================
UNIT VERIFICATION CONCLUSION (required by the locked specification §12
before implementing any solar generation calculation)
============================================================================

Endpoint used: /api/temporal/hourly/point, community=RE, time-standard=UTC.

Per NASA POWER's own Hourly API documentation
(https://power.larc.nasa.gov/docs/services/api/temporal/hourly/):
    "Provides parameters by hour with average values."

Cross-checked against `pvlib.iotools.nasa_power` (the standard open-source
PV-modeling library's NASA POWER client), which documents the Hourly Point
API's `ALLSKY_SFC_SW_DWN` parameter under the RE community explicitly as:
    "Global Horizontal Irradiance (GHI) [W/m^-2]"

CONCLUSION: For this endpoint/community, ALLSKY_SFC_SW_DWN is an HOURLY
AVERAGE IRRADIANCE in W/m^2 — not an instantaneous spot reading, and not a
pre-integrated Wh/m^2 daily-aggregate figure (a different units convention
that applies to some other NASA POWER products, but not this one).

DIMENSIONAL CONSEQUENCE: because the value is an average power (W/m^2)
sustained across exactly one hour, it is numerically equal to the energy
density (Wh/m^2) delivered in that hour (average power x 1 hour = energy).
Dividing by 1000 (the Standard Test Condition reference irradiance,
1000 W/m^2 = 1 kW/m^2, against which PV system "capacity" ratings are
defined) converts the hourly GHI value into kWh/m^2 for that hour — the
conventional "peak-sun-hours" figure used in simplified PV-capacity-based
generation formulas. This is what makes

    estimated_kwh = (ghi_w_per_m2 / 1000) * capacity_kw * performance_ratio

dimensionally sensible as a simplified prototype estimator, where
`capacity_kw` is the system's STC-rated electrical output (see
app/services/solar_generation.py for the full model rationale, including
why PV module efficiency is deliberately NOT a multiplier in this formula).
This module is only responsible for fetching, validating, and persisting
the *raw* NASA POWER values — it performs no generation estimation itself.
============================================================================

Scope of this module (Phase 2, ingestion only): URL construction, HTTP
request with timeout/retry/backoff, response validation, and cache-key
construction. Persistence orchestration lives in
app/services/nasa_power_ingestion.py.
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------
# Exceptions
# --------------------------------------------------------------------------

class NasaPowerError(Exception):
    """Base exception for all NASA POWER integration failures."""


class NasaPowerRequestError(NasaPowerError):
    """Raised for transport-level failures (timeouts, connection errors, retryable server errors)."""


class NasaPowerClientError(NasaPowerRequestError):
    """
    Raised for non-retryable 4xx responses (bad request parameters, etc).
    Kept as a distinct type from the retryable case so the retry loop can
    fail fast on it instead of burning through retries on a request that
    will never succeed.
    """


class NasaPowerValidationError(NasaPowerError):
    """Raised when a response is malformed, missing expected fields, or otherwise untrustworthy."""


# --------------------------------------------------------------------------
# Request parameters + cache key
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class NasaPowerRequestParams:
    latitude: float
    longitude: float
    start_date: str  # YYYYMMDD
    end_date: str  # YYYYMMDD
    parameters: List[str]
    community: str = settings.nasa_power_community
    time_standard: str = settings.nasa_power_time_standard
    format: str = settings.nasa_power_format

    def __post_init__(self):
        for label, value in (("start_date", self.start_date), ("end_date", self.end_date)):
            try:
                datetime.strptime(value, "%Y%m%d")
            except ValueError as exc:
                raise NasaPowerValidationError(f"{label} must be in YYYYMMDD format, got {value!r}") from exc
        if self.start_date > self.end_date:
            raise NasaPowerValidationError("start_date must not be after end_date")
        if not self.parameters:
            raise NasaPowerValidationError("At least one parameter must be requested")

    def build_url(self, base_url: Optional[str] = None) -> str:
        base = base_url or settings.nasa_power_base_url
        query = {
            "parameters": ",".join(self.parameters),
            "community": self.community,
            "longitude": self.longitude,
            "latitude": self.latitude,
            "start": self.start_date,
            "end": self.end_date,
            "format": self.format,
            "time-standard": self.time_standard,
        }
        query_str = "&".join(f"{k}={v}" for k, v in query.items())
        return f"{base}?{query_str}"

    def cache_key(self) -> str:
        """
        Deterministic cache key covering every dimension that must not be
        conflated (locked specification §15): lat, lon, parameters,
        start_date, end_date, community, time_standard.
        """
        raw = "|".join(
            [
                f"{self.latitude:.6f}",
                f"{self.longitude:.6f}",
                ",".join(sorted(self.parameters)),
                self.start_date,
                self.end_date,
                self.community,
                self.time_standard,
            ]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_cache_key(
    latitude: float,
    longitude: float,
    parameters: List[str],
    start_date: str,
    end_date: str,
    community: str = settings.nasa_power_community,
    time_standard: str = settings.nasa_power_time_standard,
) -> str:
    return NasaPowerRequestParams(
        latitude=latitude,
        longitude=longitude,
        start_date=start_date,
        end_date=end_date,
        parameters=parameters,
        community=community,
        time_standard=time_standard,
    ).cache_key()


# --------------------------------------------------------------------------
# HTTP client with retry/backoff
# --------------------------------------------------------------------------

def fetch_nasa_power(
    params: NasaPowerRequestParams,
    client: Optional[httpx.Client] = None,
) -> Dict[str, Any]:
    """
    Perform the NASA POWER Hourly Point API request with a bounded number
    of retries and exponential backoff, per the locked specification's
    request-safety requirements (§10): reasonable frequency, timeout,
    retry with backoff, no aggressive parallelism (this function issues a
    single sequential request per call).

    Raises `NasaPowerRequestError` if all retries are exhausted.
    """
    url = params.build_url()
    owns_client = client is None
    http_client = client or httpx.Client(timeout=settings.nasa_power_request_timeout_seconds)

    last_exc: Optional[Exception] = None
    try:
        for attempt in range(1, settings.nasa_power_max_retries + 1):
            try:
                logger.info("NASA POWER request attempt %s/%s: %s", attempt, settings.nasa_power_max_retries, url)
                response = http_client.get(url)
                if response.status_code >= 500:
                    # Server-side error: worth retrying.
                    raise NasaPowerRequestError(
                        f"NASA POWER server error {response.status_code}: {response.text[:500]}"
                    )
                if response.status_code >= 400:
                    # Client-side error: not worth retrying (bad params etc.), fail fast.
                    raise NasaPowerClientError(
                        f"NASA POWER request rejected ({response.status_code}): {response.text[:500]}"
                    )
                return response.json()
            except NasaPowerClientError:
                # Non-retryable: propagate immediately, do not consume a retry attempt.
                raise
            except (httpx.TimeoutException, httpx.TransportError, NasaPowerRequestError) as exc:
                last_exc = exc
                if attempt < settings.nasa_power_max_retries:
                    backoff = settings.nasa_power_retry_backoff_seconds * attempt
                    logger.warning("NASA POWER request failed (attempt %s): %s — retrying in %.1fs", attempt, exc, backoff)
                    time.sleep(backoff)
                else:
                    logger.error("NASA POWER request failed after %s attempts: %s", attempt, exc)
    finally:
        if owns_client:
            http_client.close()

    raise NasaPowerRequestError(f"NASA POWER request failed after {settings.nasa_power_max_retries} attempts") from last_exc


# --------------------------------------------------------------------------
# Response validation / parsing
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ParsedWeatherRecord:
    timestamp: datetime  # UTC
    values: Dict[str, Optional[float]]  # parameter name -> value (None if fill value)


def parse_and_validate_response(
    raw: Dict[str, Any],
    expected_parameters: List[str],
    fill_value: float = settings.nasa_power_fill_value,
) -> List[ParsedWeatherRecord]:
    """
    Validate structure and content of a NASA POWER Hourly Point API JSON
    response, and parse it into a list of per-timestamp records.

    Validates (per locked specification §11):
      - top-level JSON structure (properties.parameter present)
      - every expected parameter is present in the response
      - timestamp fields are well-formed and parseable
      - numeric values are actually numeric
      - fill-value entries are converted to None (missing), not silently
        treated as real zeros
      - no duplicate timestamps

    Raises `NasaPowerValidationError` on any structural problem. Does NOT
    raise on individual missing (fill-value) readings — those are surfaced
    as `None` in the returned record so the caller can decide how to handle
    gaps (e.g. skip, interpolate later, flag).
    """
    if not isinstance(raw, dict):
        raise NasaPowerValidationError("NASA POWER response is not a JSON object")

    # NASA POWER also returns structured error payloads under "messages"/"errors"
    # for bad requests that still come back as 200 in some cases — check first.
    if "messages" in raw and raw.get("messages"):
        raise NasaPowerValidationError(f"NASA POWER returned an error payload: {raw['messages']}")

    properties = raw.get("properties")
    if not isinstance(properties, dict):
        raise NasaPowerValidationError("Missing/invalid 'properties' in NASA POWER response")

    parameter_block = properties.get("parameter")
    if not isinstance(parameter_block, dict):
        raise NasaPowerValidationError("Missing/invalid 'properties.parameter' in NASA POWER response")

    missing_params = [p for p in expected_parameters if p not in parameter_block]
    if missing_params:
        raise NasaPowerValidationError(f"Response is missing requested parameter(s): {missing_params}")

    # Collect the full set of timestamps across all parameters, validating
    # each is parseable and there are no duplicates within a single
    # parameter's series (NASA POWER returns one dict of {timestamp: value}
    # per parameter; duplicates would mean a malformed/duplicate key,
    # which JSON itself can't represent twice in the same object, but we
    # still validate the merged timestamp set is consistent across params).
    per_param_timestamps: Dict[str, set] = {}
    for param_name in expected_parameters:
        series = parameter_block[param_name]
        if not isinstance(series, dict):
            raise NasaPowerValidationError(f"Parameter {param_name!r} series is not an object")
        ts_set = set()
        for ts_str in series.keys():
            parsed_ts = _parse_nasa_timestamp(ts_str)
            if parsed_ts is None:
                raise NasaPowerValidationError(f"Unparseable timestamp {ts_str!r} for parameter {param_name!r}")
            if ts_str in ts_set:
                raise NasaPowerValidationError(f"Duplicate timestamp {ts_str!r} for parameter {param_name!r}")
            ts_set.add(ts_str)
        per_param_timestamps[param_name] = ts_set

    # All parameters must cover the same timestamp set — otherwise records
    # would be inconsistent across columns.
    timestamp_sets = list(per_param_timestamps.values())
    if timestamp_sets and any(s != timestamp_sets[0] for s in timestamp_sets[1:]):
        raise NasaPowerValidationError("Parameters in response do not share a consistent timestamp set")

    all_timestamps = sorted(timestamp_sets[0]) if timestamp_sets else []

    records: List[ParsedWeatherRecord] = []
    for ts_str in all_timestamps:
        values: Dict[str, Optional[float]] = {}
        for param_name in expected_parameters:
            raw_value = parameter_block[param_name][ts_str]
            if not isinstance(raw_value, (int, float)):
                raise NasaPowerValidationError(
                    f"Non-numeric value for {param_name!r} at {ts_str!r}: {raw_value!r}"
                )
            values[param_name] = None if float(raw_value) == float(fill_value) else float(raw_value)
        records.append(ParsedWeatherRecord(timestamp=_parse_nasa_timestamp(ts_str), values=values))

    return records


def _parse_nasa_timestamp(ts_str: str) -> Optional[datetime]:
    """
    NASA POWER hourly timestamps are formatted YYYYMMDDHH (10 digits).
    Returned as a UTC-aware datetime (time-standard=UTC is always used per
    the locked specification §5 — this parser assumes that's what was
    requested; it does not itself set the time-standard).
    """
    if not (isinstance(ts_str, str) and len(ts_str) == 10 and ts_str.isdigit()):
        return None
    try:
        return datetime.strptime(ts_str, "%Y%m%d%H").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
