"""Pydantic schemas for load profiles endpoints."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, field_validator


class LoadProfileRead(BaseModel):
    id: int
    series_id: int
    series_name: Optional[str] = None
    methodology_version: str
    mean_demand_kw: float
    median_demand_kw: float
    min_demand_kw: float
    max_demand_kw: float
    std_demand_kw: float
    observation_count: int
    coefficient_of_variation: float
    peak_to_average_ratio: float
    day_night_ratio: Optional[float] = None
    tou_peak_overlap_pct: Optional[float] = None
    weekday_weekend_ratio: Optional[float] = None
    cluster_id: Optional[int] = None
    is_selected: bool
    distance_to_centroid: Optional[float] = None
    selection_rationale: Optional[str] = None
    weekday_shape: Optional[List[float]] = None
    weekend_shape: Optional[List[float]] = None

    model_config = ConfigDict(from_attributes=True)


class LoadProfilesListResponse(BaseModel):
    profiles: List[LoadProfileRead]
    total_count: int
    selected_count: int
    is_demo: bool = False
    explanatory_note: str = "Real load profiling results from 321 Monash electricity series profiling."
