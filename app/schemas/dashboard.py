"""Pydantic schemas for the main dashboard overview endpoint."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from app.schemas.common import DemoResponseMixin


class DashboardOverviewResponse(DemoResponseMixin):
    dataset_metrics: Dict[str, Any]
    solar_metrics: Dict[str, Any]
    battery_metrics: Dict[str, Any]
    allocation_metrics: Dict[str, Any]
    billing_metrics: Dict[str, Any]
    selected_profiles_summary: List[Dict[str, Any]]
