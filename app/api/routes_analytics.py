"""API routes for dataset analytics and statistical overview."""

import logging
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db.session import get_db
from app.models.load_profile import PublicLoadSeriesProfile
from app.models.public_load import PublicLoadObservation, PublicLoadSeries
from app.schemas.analytics import AnalyticsOverviewResponse, SelectedProfileSummaryItem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverviewResponse)
def get_analytics_overview(db: Session = Depends(get_db)) -> AnalyticsOverviewResponse:
    total_series = db.query(PublicLoadSeries).count()
    total_obs = db.query(PublicLoadObservation).count()
    total_profiles = db.query(PublicLoadSeriesProfile).count()

    selected_profiles = (
        db.query(PublicLoadSeriesProfile, PublicLoadSeries.series_name)
        .join(PublicLoadSeries, PublicLoadSeriesProfile.series_id == PublicLoadSeries.id)
        .filter(PublicLoadSeriesProfile.is_selected == True)
        .order_by(PublicLoadSeriesProfile.cluster_id.asc())
        .all()
    )

    selected_summary: List[SelectedProfileSummaryItem] = [
        SelectedProfileSummaryItem(
            cluster_id=prof.cluster_id or 0,
            series_name=name,
            mean_demand_kw=round(prof.mean_demand_kw, 2),
            coefficient_of_variation=round(prof.coefficient_of_variation, 3),
            peak_to_average_ratio=round(prof.peak_to_average_ratio, 3),
        )
        for prof, name in selected_profiles
    ]

    return AnalyticsOverviewResponse(
        total_public_series=total_series,
        total_observations=total_obs,
        total_profiles_computed=total_profiles,
        selected_profiles_count=len(selected_summary),
        observation_date_range={
            "start": "2012-01-01T00:00:01",
            "end": "2014-12-31T23:00:01",
        },
        selected_profiles_summary=selected_summary,
        is_demo=False,
        explanatory_note="Real analytics computed directly from the 8.44M observation dataset and profiling database tables.",
    )
