"""Pydantic schemas for energy allocation optimization endpoints."""

from typing import List, Optional
from pydantic import BaseModel
from app.schemas.common import DemoResponseMixin


class TenantAllocationItem(BaseModel):
    tenant_id: int
    tenant_name: str
    demanded_kw: float
    allocated_solar_kw: float
    battery_power_kw: float
    grid_power_kw: float
    fairness_share_pct: float


class AllocationCurrentResponse(DemoResponseMixin):
    timestamp: str
    total_solar_available_kw: float
    total_estate_demand_kw: float
    allocations: List[TenantAllocationItem]
    unallocated_solar_kw: float
    optimization_status: str = "OPTIMAL"
