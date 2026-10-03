"""API routes for solar PV configuration and generation estimates."""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role
from app.db.session import get_db
from app.models.config import PVConfig
from app.models.enums import UserRole
from app.models.weather import SolarGenerationEstimate, WeatherObservation
from app.schemas.solar import (
    NOCT_CELLS,
    PVConfigRead,
    SolarGenerationListResponse,
    SolarGenerationRead,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/solar", tags=["solar"])


@router.get(
    "/pv-config",
    response_model=PVConfigRead,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
def get_pv_config(
    estate_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
) -> PVConfigRead:
    query = db.query(PVConfig).filter(PVConfig.is_active == True)
    if estate_id is not None:
        query = query.filter(PVConfig.estate_id == estate_id)

    pv_config = query.order_by(PVConfig.effective_from.desc()).first()

    if pv_config is not None:
        read_model = PVConfigRead.model_validate(pv_config)
        read_model.is_demo = False
        read_model.explanatory_note = "Real PV configuration stored in database."
        return read_model

    # Demo fallback if unseeded
    return PVConfigRead(
        id=1,
        estate_id=estate_id or 1,
        capacity_kw=500.0,
        efficiency=0.20,
        performance_ratio=0.80,
        effective_from=datetime.now(timezone.utc),
        is_active=True,
        notes="Prototype PV configuration assumption (500 kW STC capacity, 80% PR).",
        is_demo=True,
        explanatory_note="Prototype demo assumption — no active PVConfig record found in database.",
    )


def _estimate_cell_temperature_c(ambient_c: Optional[float], ghi_wm2: Optional[float]) -> Optional[float]:
    """
    Estimate module cell temperature from ambient temperature and irradiance.

    Uses the standard steady-state NOCT relation that PVWatts and most PV
    engineering references apply:

        T_cell = T_ambient + (NOCT - 20) / 800 * irradiance

    with irradiance in W/m^2. This is a *documented model estimate*, not a
    measurement — SolarShare has no on-site back-of-module temperature sensor,
    so no measured cell temperature exists to report.

    GHI stands in for plane-of-array irradiance, which is a simplification: a
    real transposition model would distinguish them, and reporting an invented
    POA figure is exactly what this endpoint must not do. Returns None when
    either input is missing rather than assuming a default temperature.
    """
    if ambient_c is None or ghi_wm2 is None:
        return None
    return round(ambient_c + ((NOCT_CELLS - 20.0) / 800.0) * ghi_wm2, 2)


@router.get(
    "/generation",
    response_model=SolarGenerationListResponse,
    dependencies=[Depends(get_current_user)],
)
def get_solar_generation(
    estate_id: Optional[int] = Query(None),
    limit: int = Query(24, ge=1, le=720),
    db: Session = Depends(get_db),
) -> SolarGenerationListResponse:
    query = db.query(SolarGenerationEstimate)
    if estate_id is not None:
        query = query.filter(SolarGenerationEstimate.estate_id == estate_id)

    records = query.order_by(SolarGenerationEstimate.timestamp.desc()).limit(limit).all()

    if records:
        # Batch-load the two parents the estimate rows point at, keyed by id.
        # Two extra queries regardless of `limit`, rather than a per-record
        # lookup for every estimate row.
        weather_by_id: Dict[int, WeatherObservation] = {
            obs.id: obs
            for obs in db.query(WeatherObservation)
            .filter(WeatherObservation.id.in_({r.weather_observation_id for r in records}))
            .all()
        }
        configs_by_id: Dict[int, PVConfig] = {
            cfg.id: cfg
            for cfg in db.query(PVConfig)
            .filter(PVConfig.id.in_({r.pv_config_id for r in records}))
            .all()
        }

        reads: List[SolarGenerationRead] = []
        missing_weather = 0
        for r in records:
            obs = weather_by_id.get(r.weather_observation_id)
            cfg = configs_by_id.get(r.pv_config_id)
            if obs is None:
                missing_weather += 1

            ghi = obs.allsky_sfc_sw_dwn if obs is not None else None
            ambient = obs.t2m if obs is not None else None

            # `estimated_kwh` is the energy produced over one 1-hour interval, so
            # the average power over that same interval is numerically identical
            # (Energy = Power x Time, interval_hours == 1.0). This is a genuine
            # unit conversion, the same reasoning locked in for the public-load
            # ingestion path in app/integrations/electricity_dataset.py.
            energy_kwh = round(r.estimated_kwh, 3)

            reads.append(
                SolarGenerationRead(
                    estate_id=r.estate_id,
                    timestamp_local=r.timestamp,
                    # measured
                    ghi_wm2=ghi,
                    ambient_temperature_c=ambient,
                    pv_energy_kwh=energy_kwh,
                    # documented estimate
                    cell_temperature_c=_estimate_cell_temperature_c(ambient, ghi),
                    pv_power_kw=energy_kwh,
                    # not available from this integration — left as None
                    dni_wm2=None,
                    dhi_wm2=None,
                    poa_irradiance_wm2=None,
                    # the configuration the estimate was actually computed with
                    capacity_kw=cfg.capacity_kw if cfg is not None else None,
                    performance_ratio=cfg.performance_ratio if cfg is not None else None,
                )
            )

        if missing_weather:
            logger.warning(
                "%s of %s solar generation estimates have no matching WeatherObservation row; "
                "irradiance and temperature fields are null for those records.",
                missing_weather,
                len(records),
            )

        return SolarGenerationListResponse(
            records=reads,
            total_records=len(reads),
            is_demo=False,
            explanatory_note=(
                "Real Model B PV generation estimates derived from NASA POWER hourly "
                "observations. ghi_wm2 and ambient_temperature_c are measured (source: "
                "NASA POWER ALLSKY_SFC_SW_DWN / T2M); pv_energy_kwh and pv_power_kw are "
                "the stored estimate over a 1-hour interval; capacity_kw and "
                "performance_ratio come from the PVConfig row used to compute it; "
                "cell_temperature_c is a NOCT model estimate, not a measurement. "
                "dni_wm2, dhi_wm2 and poa_irradiance_wm2 are null because this "
                "integration neither retrieves nor models them."
            ),
        )

    # Demo fallback curve (24 hours bell curve)
    now = datetime.now()
    demo_records: List[SolarGenerationRead] = []
    # 500 kW system, peak ~380 kW around noon
    hourly_kw_factors = [
        0, 0, 0, 0, 0, 0,
        0.05, 0.20, 0.45, 0.70, 0.88, 0.96,
        1.00, 0.95, 0.85, 0.65, 0.38, 0.15,
        0.02, 0, 0, 0, 0, 0
    ]

    for h, factor in enumerate(hourly_kw_factors):
        ts = datetime(now.year, now.month, now.day, h, 0, 0)
        power_kw = round(380.0 * factor, 2)
        demo_records.append(
            SolarGenerationRead(
                estate_id=estate_id or 1,
                timestamp_local=ts,
                ghi_wm2=round(900.0 * factor, 1),
                dni_wm2=round(800.0 * factor, 1),
                dhi_wm2=round(150.0 * factor, 1),
                ambient_temperature_c=round(25.0, 1),
                cell_temperature_c=round(25.0 + 15.0 * factor, 1),
                poa_irradiance_wm2=round(950.0 * factor, 1),
                pv_power_kw=power_kw,
                pv_energy_kwh=power_kw,  # 1 hour interval
                capacity_kw=500.0,
                performance_ratio=0.80,
            )
        )

    return SolarGenerationListResponse(
        records=demo_records,
        total_records=len(demo_records),
        is_demo=True,
        explanatory_note="Illustrative 24-hour solar generation curve (no persisted solar generation records in DB yet).",
    )
