"""Pydantic schemas for dataset and estate analytics endpoints."""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel
from app.schemas.common import DemoResponseMixin


class SelectedProfileSummaryItem(BaseModel):
    cluster_id: int
    series_name: str
    mean_demand_kw: float
    coefficient_of_variation: float
    peak_to_average_ratio: float


class AnalyticsOverviewResponse(BaseModel):
    total_public_series: int
    total_observations: int
    total_profiles_computed: int
    selected_profiles_count: int
    observation_date_range: Dict[str, str]
    selected_profiles_summary: List[SelectedProfileSummaryItem]
    is_demo: bool = False
    explanatory_note: str = "Real analytics computed directly from the 8.44M row SQLite database."
