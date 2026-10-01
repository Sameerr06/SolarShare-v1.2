"""API routes for solar PV configuration and generation estimates."""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.config import PVConfig
from app.models.weather import SolarGenerationEstimate
from app.schemas.solar import PVConfigRead, SolarGenerationListResponse, SolarGenerationRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/solar", tags=["solar"])


@router.get("/pv-config", response_model=PVConfigRead)
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


@router.get("/generation", response_model=SolarGenerationListResponse)
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
        reads = [
            SolarGenerationRead(
                estate_id=r.estate_id,
                timestamp_local=r.timestamp,
                ghi_wm2=0.0,
                dni_wm2=0.0,
                dhi_wm2=0.0,
                cell_temperature_c=25.0,
                poa_irradiance_wm2=0.0,
                pv_power_kw=r.estimated_kwh,
                pv_energy_kwh=r.estimated_kwh,
                capacity_kw=500.0,
                performance_ratio=0.80,
            )
            for r in records
        ]
        return SolarGenerationListResponse(
            records=reads,
            total_records=len(reads),
            is_demo=False,
            explanatory_note="Real solar generation estimates from NASA POWER weather data.",
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
