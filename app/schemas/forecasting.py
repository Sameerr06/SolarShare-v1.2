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
    # Set ONLY when the response was produced by the demo fallback instead of a
    # trained model, and carries the underlying failure so the degradation is
    # visible to the operator and to the client UI rather than hidden behind a
    # plausible-looking curve. None on the real path.
    fallback_reason: Optional[str] = None


class TenantForecastResponse(DemoResponseMixin):
    tenant_id: int
    tenant_name: str
    forecast_period_hours: int
    forecast_data: List[ForecastDataPoint]
    total_consumption_forecast_kwh: float
    peak_demand_kw: float
    model_name: str = "Prophet"
    training_record_count: Optional[int] = None
    # See SolarForecastResponse.fallback_reason.
    fallback_reason: Optional[str] = None
