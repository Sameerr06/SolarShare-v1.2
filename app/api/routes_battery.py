"""API routes for battery storage system configuration and real-time status."""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.config import BatteryConfig
from app.schemas.battery import BatteryConfigRead, BatteryStatusResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/battery", tags=["battery"])


@router.get("/config", response_model=BatteryConfigRead)
def get_battery_config(
    estate_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
) -> BatteryConfigRead:
    query = db.query(BatteryConfig).filter(BatteryConfig.is_active == True)
    if estate_id is not None:
        query = query.filter(BatteryConfig.estate_id == estate_id)

    b_config = query.order_by(BatteryConfig.effective_from.desc()).first()

    if b_config is not None:
        read_model = BatteryConfigRead.model_validate(b_config)
        read_model.is_demo = False
        read_model.explanatory_note = "Real battery configuration stored in database."
        return read_model

    # Demo fallback if unseeded
    return BatteryConfigRead(
        id=1,
        estate_id=estate_id or 1,
        capacity_kwh=200.0,
        initial_soc_pct=50.0,
        min_soc_pct=10.0,
        max_soc_pct=90.0,
        max_charge_kw=50.0,
        max_discharge_kw=50.0,
        round_trip_efficiency=0.90,
        effective_from=datetime.now(timezone.utc),
        is_active=True,
        notes="Prototype battery configuration assumption (200 kWh capacity, 90% RTE).",
        is_demo=True,
        explanatory_note="Prototype demo assumption — no active BatteryConfig record found in database.",
    )


@router.get("/status", response_model=BatteryStatusResponse)
def get_battery_status(
    estate_id: int = Query(1, ge=1),
    db: Session = Depends(get_db),
) -> BatteryStatusResponse:
    # Query battery config if present to set capacity
    b_config = db.query(BatteryConfig).filter(BatteryConfig.is_active == True).first()
    capacity = b_config.capacity_kwh if b_config else 200.0

    return BatteryStatusResponse(
        estate_id=estate_id,
        current_soc_pct=68.5,
        current_stored_kwh=round(capacity * 0.685, 2),
        capacity_kwh=capacity,
        current_power_kw=25.0,  # + = discharging, - = charging
        operation_mode="DISCHARGING",
        health_soh_pct=98.2,
        is_demo=True,
        explanatory_note="Prototype demo response — real-time battery simulation state loop is not yet connected.",
    )
