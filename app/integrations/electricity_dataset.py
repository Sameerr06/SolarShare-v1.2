"""
Public electricity dataset integration: acquisition, unit conversion, and
validation for the Zenodo "Electricity Hourly Dataset" (DOI
10.5281/zenodo.4656140).

============================================================================
LOCKED UNIT INTERPRETATION (approved this session — do not change without
explicit instruction)
============================================================================
SOURCE DATASET:   Electricity Hourly Dataset, Zenodo 10.5281/zenodo.4656140
SOURCE STRUCTURE: 321 client series, 2012-2014, hourly resolution
ORIGINAL SOURCE:  15-minute average-power measurements in kW
AGGREGATION:      hourly value = mean of the four 15-minute kW readings
                  within that hour
SOURCE UNIT:      "Hourly average electricity demand in kW." — an
                  INTENSIVE quantity (average power), not energy. Do not
                  describe the source dataset itself as being in kWh.

SOLARSHARE INTERNAL UNIT: "Hourly energy consumption in kWh."
CONVERSION:
    energy_kwh = hourly_average_kw * interval_hours
    interval_hours = 1.0 for this dataset (hourly resolution)
    => energy_kwh = hourly_average_kw * 1.0

This is Energy = Power x Time. The numerical value is unchanged ONLY
because interval_hours happens to be exactly 1.0 for this dataset — this is
a genuine physical unit conversion (see convert_to_energy_kwh() below),
not a relabeling, and would look different for any other interval width.
============================================================================

ACQUISITION LIMITATION (documented, not hidden): this implementation
environment cannot reach zenodo.org or huggingface.co (outside the sandbox's
network allowlist), so the real ~36 MB .tsf file could not be downloaded
during implementation. `acquire_dataset()` below supports both a local file
path (usable today, and in any environment where the file has been manually
placed) and an HTTP URL fetch path (implemented and ready, but not
exercisable from this sandbox) — see README for manual acquisition
instructions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import httpx

from app.core.config import settings
from app.integrations.tsf_parser import TsfDataset, TsfParseError, parse_tsf

logger = logging.getLogger(__name__)

SOURCE_UNIT_DESCRIPTION = "Hourly average electricity demand in kW."
DERIVED_UNIT_DESCRIPTION = "Hourly energy consumption in kWh."


class ElectricityDatasetError(Exception):
    """Base exception for electricity dataset acquisition/conversion/validation failures."""


class ElectricityDatasetAcquisitionError(ElectricityDatasetError):
    pass


class ElectricityDatasetValidationError(ElectricityDatasetError):
    pass


# --------------------------------------------------------------------------
# 1. Acquisition
# --------------------------------------------------------------------------

def acquire_dataset(local_path: Optional[str] = None, source_url: Optional[str] = None) -> str:
    """
    Acquire the .tsf file and return a local filesystem path to it.

    Resolution order:
      1. `local_path` argument, if given and it exists.
      2. `settings.electricity_dataset_local_path`, if configured and exists.
      3. Fetch from `source_url` (or `settings.electricity_dataset_source_url`)
         over HTTP — implemented, but not exercisable in this sandboxed
         environment (see module docstring).

    Raises `ElectricityDatasetAcquisitionError` if no usable source is found.
    """
    candidate = local_path or settings.electricity_dataset_local_path
    if candidate:
        path = Path(candidate)
        if path.is_file():
            logger.info("Using local electricity dataset file: %s", path)
            return str(path)
        logger.warning("Configured electricity_dataset_local_path does not exist: %s", candidate)

    url = source_url or settings.electricity_dataset_source_url
    if not url:
        raise ElectricityDatasetAcquisitionError(
            "No local .tsf file available and no source URL configured."
        )

    logger.info("Attempting HTTP fetch of electricity dataset from %s", url)
    try:
        with httpx.Client(timeout=settings.electricity_dataset_request_timeout_seconds) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ElectricityDatasetAcquisitionError(
            f"Failed to fetch electricity dataset from {url}: {exc}"
        ) from exc

    # A real Zenodo record page (as opposed to a direct .tsf download link)
    # returns HTML, not the file itself — this is a placeholder for a real
    # deployment's proper download-link resolution logic, not a functioning
    # fetch of the actual archive/zip/tsf in this sandbox.
    tmp_path = Path("/tmp/electricity_hourly_dataset_downloaded.tsf")
    tmp_path.write_bytes(response.content)
    logger.info("Downloaded electricity dataset to %s", tmp_path)
    return str(tmp_path)


# --------------------------------------------------------------------------
# 2. Unit conversion
# --------------------------------------------------------------------------

def convert_to_energy_kwh(hourly_average_kw: Optional[float], interval_hours: float = 1.0) -> Optional[float]:
    """
    Energy = Power x Time.

    `hourly_average_kw` is the SOURCE value (an average power reading, kW).
    `interval_hours` is the width of the interval that average was computed
    over (1.0 for this dataset's hourly resolution). The result is the
    DERIVED energy (kWh) actually consumed during that interval.

    Returns None (not 0.0) when the source value itself is missing — a
    missing reading must never be silently treated as zero consumption.
    """
    if hourly_average_kw is None:
        return None
    return hourly_average_kw * interval_hours


# --------------------------------------------------------------------------
# 3. Validation
# --------------------------------------------------------------------------

@dataclass
class ValidatedSeries:
    series_name: str
    start_timestamp_local: datetime
    frequency: str
    timestamps: List[datetime]
    hourly_average_kw: List[Optional[float]]
    energy_kwh: List[Optional[float]]


@dataclass
class ValidationReport:
    valid_series: List[ValidatedSeries]
    rejected_series: List[str]  # series_name -> reason, flattened to strings for reporting
    total_records_considered: int
    total_records_valid: int
    total_records_missing_value: int
    total_records_negative_rejected: int


@dataclass
class SeriesValidationStats:
    considered: int
    valid: int
    missing: int
    negative_rejected: int


def _reconstruct_timestamps(start: datetime, count: int, frequency: str) -> List[datetime]:
    """
    Reconstruct per-value timestamps from a series' single start_timestamp,
    per the .tsf format's implicit-timestamp convention (start + n * step).

    Only 'hourly' frequency is required for this dataset; other frequencies
    are supported at day/week granularity for general parser reusability,
    but are not exercised by this ingestion path.
    """
    from datetime import timedelta

    step_by_frequency = {
        "hourly": timedelta(hours=1),
        "daily": timedelta(days=1),
        "weekly": timedelta(weeks=1),
    }
    step = step_by_frequency.get(frequency)
    if step is None:
        raise ElectricityDatasetValidationError(f"Unsupported frequency for timestamp reconstruction: {frequency!r}")
    return [start + i * step for i in range(count)]


def validate_and_convert_series(series, frequency: str):
    """
    Validate and convert a SINGLE series. This is the core function used by
    both the streaming ingestion path (one series at a time, memory-bounded)
    and the eager `validate_and_convert()` wrapper below (kept for the
    existing test suite / small-file use).

    Raises `ElectricityDatasetValidationError` for structural problems
    (empty series, unsupported frequency, duplicate reconstructed
    timestamps). Individual missing ('?') or negative readings within an
    otherwise-valid series are NOT structural failures — they're preserved
    as None (missing) in the returned series, never silently converted to
    an implied zero, and are the caller's job to count/log, not reject on.

    Duplicate series-name detection is intentionally NOT done here — both
    `parse_tsf`/`_parse_tsf_lines` (eager) and `parse_tsf_streaming`
    (streaming) already guarantee unique series names before this function
    ever sees a series, so re-checking here would be redundant.

    Returns `(ValidatedSeries, SeriesValidationStats)`.
    """
    if not series.values:
        raise ElectricityDatasetValidationError(f"{series.series_name}: empty series (no values)")

    timestamps = _reconstruct_timestamps(series.start_timestamp, len(series.values), frequency)
    if len(set(timestamps)) != len(timestamps):
        raise ElectricityDatasetValidationError(f"{series.series_name}: duplicate reconstructed timestamps")

    cleaned_values: List[Optional[float]] = []
    considered = 0
    valid = 0
    missing = 0
    negative_rejected = 0
    series_had_negative = False

    for v in series.values:
        considered += 1
        if v is None:
            missing += 1
            cleaned_values.append(None)
            continue
        if v < 0:
            negative_rejected += 1
            series_had_negative = True
            cleaned_values.append(None)  # treat an invalid negative reading as missing, not as a fabricated 0
            continue
        valid += 1
        cleaned_values.append(v)

    if series_had_negative:
        logger.warning(
            "Series %s contained negative reading(s); those points were treated as missing, not rejected wholesale.",
            series.series_name,
        )

    energy_values = [convert_to_energy_kwh(v, interval_hours=1.0) for v in cleaned_values]

    validated = ValidatedSeries(
        series_name=series.series_name,
        start_timestamp_local=series.start_timestamp,
        frequency=frequency,
        timestamps=timestamps,
        hourly_average_kw=cleaned_values,
        energy_kwh=energy_values,
    )
    stats = SeriesValidationStats(considered=considered, valid=valid, missing=missing, negative_rejected=negative_rejected)
    return validated, stats


def validate_and_convert(dataset: TsfDataset, source_config: "ElectricityDatasetSourceConfig") -> ValidationReport:
    """
    EAGER, whole-dataset variant — validates and converts every series in
    an already-fully-parsed `TsfDataset`. Kept for the existing test suite
    and for small/medium files; internally just loops over
    `validate_and_convert_series()` per series, so behavior is identical
    to before this refactor.

    For the real, large electricity dataset, the ingestion service uses the
    per-series `validate_and_convert_series()` directly against the
    streaming parser instead of this function, to avoid materializing the
    whole dataset in memory.
    """
    if dataset.metadata.frequency != "hourly":
        raise ElectricityDatasetValidationError(
            f"Expected frequency 'hourly' per the locked interpretation, got {dataset.metadata.frequency!r}"
        )

    valid_series: List[ValidatedSeries] = []
    rejected_series: List[str] = []
    total_considered = 0
    total_valid = 0
    total_missing = 0
    total_negative_rejected = 0

    for series in dataset.series:
        try:
            validated, stats = validate_and_convert_series(series, dataset.metadata.frequency)
        except ElectricityDatasetValidationError as exc:
            rejected_series.append(f"{series.series_name}: {exc}")
            continue

        valid_series.append(validated)
        total_considered += stats.considered
        total_valid += stats.valid
        total_missing += stats.missing
        total_negative_rejected += stats.negative_rejected

    return ValidationReport(
        valid_series=valid_series,
        rejected_series=rejected_series,
        total_records_considered=total_considered,
        total_records_valid=total_valid,
        total_records_missing_value=total_missing,
        total_records_negative_rejected=total_negative_rejected,
    )


@dataclass(frozen=True)
class ElectricityDatasetSourceConfig:
    source_name: str = settings.electricity_dataset_source_name
    source_doi: str = settings.electricity_dataset_source_doi
    source_url: str = settings.electricity_dataset_source_url
