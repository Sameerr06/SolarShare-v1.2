"""Pydantic schemas for solar and tenant load forecasting endpoints."""

from typing import List, Optional
from pydantic import BaseModel
from app.schemas.common import DemoResponseMixin


class ForecastDataPoint(BaseModel):
    timestamp: str
    predicted_value_kw: float
    lower_bound_kw: float
    upper_bound_kw: float


class SolarForecastResponse(DemoResponseMixin):
    estate_id: int
    forecast_period_hours: int
    forecast_data: List[ForecastDataPoint]
    total_generation_forecast_kwh: float
    peak_generation_kw: float
    model_name: str = "Prophet"
    training_record_count: Optional[int] = None
    training_start_date: Optional[str] = None
    training_end_date: Optional[str] = None
    generated_at: Optional[str] = None


class TenantForecastResponse(DemoResponseMixin):
    tenant_id: int
    tenant_name: str
    forecast_period_hours: int
    forecast_data: List[ForecastDataPoint]
    total_consumption_forecast_kwh: float
    peak_demand_kw: float
