"""Pydantic schemas for battery storage configuration and status endpoints."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.common import DemoResponseMixin


class BatteryConfigRead(BaseModel):
    id: int
    estate_id: int
    capacity_kwh: float
    initial_soc_pct: float
    min_soc_pct: float
    max_soc_pct: float
    max_charge_kw: float
    max_discharge_kw: float
    round_trip_efficiency: float
    effective_from: datetime
    is_active: bool
    notes: str
    is_demo: bool = False
    explanatory_note: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BatteryStatusResponse(DemoResponseMixin):
    estate_id: int
    current_soc_pct: float
    current_stored_kwh: float
    capacity_kwh: float
    current_power_kw: float
    operation_mode: str
    health_soh_pct: float
