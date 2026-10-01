"""Pydantic schemas for Tamil Nadu ToU billing endpoints."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.common import DemoResponseMixin


class TariffPeriodRead(BaseModel):
    id: int
    period_name: str
    start_time: str
    end_time: str
    base_energy_charge_inr_per_kwh: float
    electricity_tax_pct: float
    effective_rate_inr_per_kwh: float

    model_config = ConfigDict(from_attributes=True)


class TariffRead(BaseModel):
    id: int
    name: str
    category: str
    effective_from: datetime
    source: str
    source_reference: str
    label: str
    periods: List[TariffPeriodRead]
    is_demo: bool = False
    explanatory_note: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class BillingTenantSummary(BaseModel):
    tenant_id: int
    tenant_name: str
    total_consumption_kwh: float
    solar_consumed_kwh: float
    grid_consumed_kwh: float
    solar_cost_inr: float
    grid_cost_inr: float
    total_bill_inr: float
    savings_inr: float


class BillingSummaryResponse(DemoResponseMixin):
    billing_period: str
    total_estate_consumption_kwh: float
    total_solar_consumed_kwh: float
    total_grid_consumed_kwh: float
    total_solar_cost_inr: float
    total_grid_cost_inr: float
    total_savings_inr: float
    tenants: List[BillingTenantSummary]
