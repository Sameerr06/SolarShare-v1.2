"""API routes for 321->6 load profiling results."""

import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.load_profile import PublicLoadSeriesProfile
from app.models.public_load import PublicLoadSeries
from app.schemas.load_profiles import LoadProfileRead, LoadProfilesListResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/load-profiles", tags=["load-profiles"])


def _to_profile_read(profile: PublicLoadSeriesProfile, series_name: Optional[str] = None) -> LoadProfileRead:
    weekday_shape = None
    if profile.weekday_shape_json:
        try:
            weekday_shape = json.loads(profile.weekday_shape_json)
        except Exception:
            weekday_shape = None

    weekend_shape = None
    if profile.weekend_shape_json:
        try:
            weekend_shape = json.loads(profile.weekend_shape_json)
        except Exception:
            weekend_shape = None

    return LoadProfileRead(
        id=profile.id,
        series_id=profile.series_id,
        series_name=series_name,
        methodology_version=profile.methodology_version,
        mean_demand_kw=profile.mean_demand_kw,
        median_demand_kw=profile.median_demand_kw,
        min_demand_kw=profile.min_demand_kw,
        max_demand_kw=profile.max_demand_kw,
        std_demand_kw=profile.std_demand_kw,
        observation_count=profile.observation_count,
        coefficient_of_variation=profile.coefficient_of_variation,
        peak_to_average_ratio=profile.peak_to_average_ratio,
        day_night_ratio=profile.day_night_ratio,
        tou_peak_overlap_pct=profile.tou_peak_overlap_pct,
        weekday_weekend_ratio=profile.weekday_weekend_ratio,
        cluster_id=profile.cluster_id,
        is_selected=profile.is_selected,
        distance_to_centroid=profile.distance_to_centroid,
        selection_rationale=profile.selection_rationale,
        weekday_shape=weekday_shape,
        weekend_shape=weekend_shape,
    )


@router.get("", response_model=LoadProfilesListResponse)
def list_load_profiles(
    selected_only: bool = Query(False, description="If True, return only the 6 selected profiles"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> LoadProfilesListResponse:
    query = (
        db.query(PublicLoadSeriesProfile, PublicLoadSeries.series_name)
        .join(PublicLoadSeries, PublicLoadSeriesProfile.series_id == PublicLoadSeries.id)
    )

    if selected_only:
        query = query.filter(PublicLoadSeriesProfile.is_selected == True)

    total_count = db.query(PublicLoadSeriesProfile).count()
    selected_count = db.query(PublicLoadSeriesProfile).filter(PublicLoadSeriesProfile.is_selected == True).count()

    results = query.order_by(PublicLoadSeriesProfile.cluster_id.asc(), PublicLoadSeriesProfile.series_id.asc()).offset(offset).limit(limit).all()

    profile_reads = [_to_profile_read(prof, name) for prof, name in results]

    return LoadProfilesListResponse(
        profiles=profile_reads,
        total_count=total_count,
        selected_count=selected_count,
        is_demo=False,
        explanatory_note="Real 321->6 load profiling dataset results retrieved directly from database.",
    )


@router.get("/selected", response_model=List[LoadProfileRead])
def get_selected_profiles(db: Session = Depends(get_db)) -> List[LoadProfileRead]:
    results = (
        db.query(PublicLoadSeriesProfile, PublicLoadSeries.series_name)
        .join(PublicLoadSeries, PublicLoadSeriesProfile.series_id == PublicLoadSeries.id)
        .filter(PublicLoadSeriesProfile.is_selected == True)
        .order_by(PublicLoadSeriesProfile.cluster_id.asc())
        .all()
    )

    return [_to_profile_read(prof, name) for prof, name in results]


@router.get("/{series_identifier}", response_model=LoadProfileRead)
def get_load_profile_by_id_or_name(
    series_identifier: str,
    db: Session = Depends(get_db),
) -> LoadProfileRead:
    # Try by series_id if numeric, or series_name
    query = db.query(PublicLoadSeriesProfile, PublicLoadSeries.series_name).join(
        PublicLoadSeries, PublicLoadSeriesProfile.series_id == PublicLoadSeries.id
    )

    result = None
    if series_identifier.isdigit():
        result = query.filter(PublicLoadSeriesProfile.series_id == int(series_identifier)).first()

    if result is None:
        result = query.filter(PublicLoadSeries.series_name == series_identifier).first()

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Load profile for series '{series_identifier}' not found.",
        )

    prof, name = result
    return _to_profile_read(prof, name)
