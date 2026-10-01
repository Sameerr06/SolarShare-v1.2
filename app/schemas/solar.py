"""Pydantic schemas for solar PV generation and configuration endpoints."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class PVConfigRead(BaseModel):
    id: int
    estate_id: int
    capacity_kw: float
    efficiency: float
    performance_ratio: float
    effective_from: datetime
    is_active: bool
    notes: str
    is_demo: bool = False
    explanatory_note: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SolarGenerationRead(BaseModel):
    estate_id: int
    timestamp_local: datetime
    ghi_wm2: float
    dni_wm2: float
    dhi_wm2: float
    cell_temperature_c: float
    poa_irradiance_wm2: float
    pv_power_kw: float
    pv_energy_kwh: float
    capacity_kw: float
    performance_ratio: float

    model_config = ConfigDict(from_attributes=True)


class SolarGenerationListResponse(BaseModel):
    records: List[SolarGenerationRead]
    total_records: int
    is_demo: bool
    explanatory_note: str
