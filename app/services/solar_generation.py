"""
Solar generation estimation — converts a raw NASA POWER GHI reading into
SolarShare's estimated electrical generation figure.

============================================================================
FORMULA AND UNIT CONVERSION (see app/integrations/nasa_power.py module
docstring for the full unit-verification writeup this depends on)
============================================================================

Input: `allsky_sfc_sw_dwn` — hourly average GHI in W/m^2 (verified against
NASA POWER's own Hourly API docs + pvlib's NASA POWER client mapping).

Step 1 — convert to kWh/m^2 for the hour:
    ghi_kwh_per_m2 = ghi_w_per_m2 / 1000

    (An average power of X W/m^2 sustained for exactly 1 hour delivers
    X Wh/m^2 of energy; dividing by 1000 expresses this in kWh/m^2. Because
    PV systems are RATED in kW at the Standard Test Condition irradiance of
    1000 W/m^2 = 1 kW/m^2, this kWh/m^2 figure is numerically equivalent to
    "hours of full-intensity sun" for that hour — the standard input to
    capacity-based PV estimation formulas.)

Step 2 — apply the generation formula (MODEL B, locked as of the Phase 2
solar-generation-model review):
    estimated_kwh = ghi_kwh_per_m2 * capacity_kw * performance_ratio

MODEL B RATIONALE (why PV efficiency is NOT a multiplier here): `capacity_kw`
is the STANDARD INDUSTRY MEANING of "PV system capacity" — the system's
rated electrical output at Standard Test Conditions, i.e. the number that
appears on a vendor spec sheet, a tender document, or a grid interconnection
agreement. Module efficiency is *already baked into* how that STC rating was
derived (panel efficiency x panel area x panel count = rated kW), so
re-applying `efficiency` as a second multiplier here would double-count that
loss and understate generation (a 500 kW system would appear to only ever
produce like a 100 kW system at full sun). `performance_ratio` alone is
responsible for capturing *additional*, real-world derating on top of the
STC rating (temperature, wiring, inverter, soiling, mismatch losses) — this
is the same structure as the widely-used PVWatts-style simplified estimator:
    Energy = Rated Capacity x (Incident Irradiance / STC Irradiance) x PR

PV module efficiency (`PVConfig.efficiency`, e.g. 0.20 / 20%) is retained in
configuration as DESCRIPTIVE METADATA ONLY — it documents how the rated
capacity is physically achieved (panel technology, approximate area implied
by that efficiency at that capacity) and is useful for realism/UI/judge
questions about installation footprint. It is deliberately NOT read by this
calculation.

Previously implemented model (superseded — kept here only as a historical
note, not in effect): an earlier version of this module additionally
multiplied by `efficiency`, treating `capacity_kw` as a pre-efficiency
theoretical maximum rather than the STC-rated output. That formulation was
reviewed, found to be physically inconsistent with how "500 kW PV capacity"
is used industry-wide, and replaced with Model B above.

This remains a documented SIMPLIFICATION, not a full physical PV simulation
(no temperature derating curve, shading, degradation, or inverter-efficiency
curve modeling) — consistent with the locked specification's requirement
that the system "must not falsely claim that this is a complete physical
photovoltaic simulation."
============================================================================
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.models.config import PVConfig
from app.models.weather import SolarGenerationEstimate, WeatherObservation

logger = logging.getLogger(__name__)

STC_REFERENCE_IRRADIANCE_W_PER_M2 = 1000.0


def estimate_generation_kwh(ghi_w_per_m2: float, pv_config: PVConfig) -> float:
    """
    Pure calculation: GHI (W/m^2, hourly average) + PVConfig -> estimated kWh
    for that hour. No I/O; safe to unit test directly against known inputs.

    MODEL B: capacity_kw is the STC-rated system output; efficiency is NOT
    used here (descriptive metadata only — see module docstring).
    """
    if ghi_w_per_m2 < 0:
        raise ValueError(f"GHI cannot be negative, got {ghi_w_per_m2}")

    ghi_kwh_per_m2 = ghi_w_per_m2 / STC_REFERENCE_IRRADIANCE_W_PER_M2
    return ghi_kwh_per_m2 * pv_config.capacity_kw * pv_config.performance_ratio


def estimate_for_observation(
    db: Session,
    observation: WeatherObservation,
    pv_config: PVConfig,
    persist: bool = True,
) -> Optional[SolarGenerationEstimate]:
    """
    Compute (and optionally persist) a SolarGenerationEstimate for a single
    WeatherObservation. Returns None (and does not persist) if the
    observation has no GHI reading for that hour (a missing/fill-value
    reading, already normalized to None during ingestion validation) —
    silently fabricating a zero would misrepresent a data gap as "no sun".
    """
    if observation.allsky_sfc_sw_dwn is None:
        logger.warning(
            "Skipping generation estimate for estate_id=%s ts=%s: no GHI reading (missing/fill value).",
            observation.estate_id, observation.timestamp,
        )
        return None

    estimated_kwh = estimate_generation_kwh(observation.allsky_sfc_sw_dwn, pv_config)

    existing = (
        db.query(SolarGenerationEstimate)
        .filter(
            SolarGenerationEstimate.estate_id == observation.estate_id,
            SolarGenerationEstimate.timestamp == observation.timestamp,
        )
        .first()
    )
    target = existing or SolarGenerationEstimate(
        estate_id=observation.estate_id,
        timestamp=observation.timestamp,
        weather_observation_id=observation.id,
        pv_config_id=pv_config.id,
    )
    target.estimated_kwh = estimated_kwh
    target.pv_config_id = pv_config.id
    target.weather_observation_id = observation.id

    if persist:
        if existing is None:
            db.add(target)
        db.commit()
        db.refresh(target)

    return target


def estimate_for_range(
    db: Session,
    estate_id: int,
    pv_config: PVConfig,
) -> int:
    """
    Batch version: estimate generation for every WeatherObservation of an
    estate that doesn't yet have a matching SolarGenerationEstimate.
    Returns the number of estimates written.
    """
    observations = (
        db.query(WeatherObservation)
        .filter(WeatherObservation.estate_id == estate_id)
        .order_by(WeatherObservation.timestamp)
        .all()
    )
    written = 0
    for obs in observations:
        if obs.allsky_sfc_sw_dwn is None:
            continue
        existing = (
            db.query(SolarGenerationEstimate)
            .filter(
                SolarGenerationEstimate.estate_id == obs.estate_id,
                SolarGenerationEstimate.timestamp == obs.timestamp,
            )
            .first()
        )
        target = existing or SolarGenerationEstimate(
            estate_id=obs.estate_id,
            timestamp=obs.timestamp,
            weather_observation_id=obs.id,
            pv_config_id=pv_config.id,
        )
        target.estimated_kwh = estimate_generation_kwh(obs.allsky_sfc_sw_dwn, pv_config)
        target.pv_config_id = pv_config.id
        target.weather_observation_id = obs.id

        if existing is None:
            db.add(target)
        written += 1

    db.commit()
    return written

