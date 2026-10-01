"""API routes for combined dashboard overview."""

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.load_profile import PublicLoadSeriesProfile
from app.models.public_load import PublicLoadObservation, PublicLoadSeries
from app.schemas.dashboard import DashboardOverviewResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/overview", response_model=DashboardOverviewResponse)
def get_dashboard_overview(db: Session = Depends(get_db)) -> DashboardOverviewResponse:
    # 1. Dataset metrics (REAL)
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

    profiles_summary = [
        {
            "cluster_id": prof.cluster_id,
            "series_name": name,
            "mean_demand_kw": round(prof.mean_demand_kw, 2),
            "cv": round(prof.coefficient_of_variation, 3),
            "par": round(prof.peak_to_average_ratio, 3),
        }
        for prof, name in selected_profiles
    ]

    dataset_metrics = {
        "total_series": total_series,
        "total_observations": total_obs,
        "total_profiles_computed": total_profiles,
        "selected_profiles_count": len(profiles_summary),
        "is_real_data": True,
    }

    # 2. Solar metrics (REAL PV config / DEMO live metrics)
    solar_metrics = {
        "installed_capacity_kw": 500.0,
        "current_generation_kw": 320.0,
        "today_generation_kwh": 2450.0,
        "performance_ratio": 0.80,
    }

    # 3. Battery metrics (DEMO)
    battery_metrics = {
        "capacity_kwh": 200.0,
        "current_soc_pct": 68.5,
        "stored_energy_kwh": 137.0,
        "status": "DISCHARGING",
        "power_kw": 25.0,
    }

    # 4. Allocation metrics (DEMO)
    allocation_metrics = {
        "active_tenants": 5,
        "total_estate_demand_kw": 500.0,
        "solar_coverage_pct": 64.0,
        "grid_dependency_pct": 31.0,
        "battery_contribution_pct": 5.0,
    }

    # 5. Billing metrics (DEMO)
    billing_metrics = {
        "current_period": "2026-08",
        "estimated_monthly_savings_inr": 210000.0,
        "solar_tariff_inr_per_kwh": 5.00,
        "average_grid_tou_rate_inr_per_kwh": 8.50,
    }

    return DashboardOverviewResponse(
        dataset_metrics=dataset_metrics,
        solar_metrics=solar_metrics,
        battery_metrics=battery_metrics,
        allocation_metrics=allocation_metrics,
        billing_metrics=billing_metrics,
        selected_profiles_summary=profiles_summary,
        is_demo=True,
        explanatory_note="Dashboard overview combines real dataset/profiling statistics with prototype demo values for active operational metrics.",
    )
