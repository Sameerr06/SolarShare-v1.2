"""API routes for fair solar energy allocation optimization (PuLP model integration scope)."""

import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.tenant import Tenant
from app.schemas.allocation import AllocationCurrentResponse, TenantAllocationItem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/allocation", tags=["allocation"])


@router.get("/current", response_model=AllocationCurrentResponse)
def get_current_allocation(db: Session = Depends(get_db)) -> AllocationCurrentResponse:
    tenants = db.query(Tenant).all()
    now_str = datetime.now().strftime("%Y-%m-%dT%H:00:00")

    total_solar = 320.0  # kW current solar generation
    total_demand = 0.0

    demo_tenants_data = [
        ("Textile Manufacturing", 180.0, 0.35),
        ("Food Processing", 120.0, 0.25),
        ("Electronics Manufacturing", 90.0, 0.18),
        ("Packaging Unit", 60.0, 0.12),
        ("General Manufacturing", 50.0, 0.10),
    ]

    allocations: List[TenantAllocationItem] = []

    for i, (name, demand_kw, share) in enumerate(demo_tenants_data, start=1):
        total_demand += demand_kw
        solar_alloc = round(min(demand_kw, total_solar * share), 2)
        battery_power = round(min(demand_kw - solar_alloc, 15.0), 2)
        grid_power = round(max(0.0, demand_kw - solar_alloc - battery_power), 2)

        allocations.append(
            TenantAllocationItem(
                tenant_id=i,
                tenant_name=name,
                demanded_kw=demand_kw,
                allocated_solar_kw=solar_alloc,
                battery_power_kw=battery_power,
                grid_power_kw=grid_power,
                fairness_share_pct=round(share * 100, 1),
            )
        )

    sum_solar_allocated = sum(a.allocated_solar_kw for a in allocations)
    unallocated_solar = max(0.0, round(total_solar - sum_solar_allocated, 2))

    return AllocationCurrentResponse(
        timestamp=now_str,
        total_solar_available_kw=total_solar,
        total_estate_demand_kw=total_demand,
        allocations=allocations,
        unallocated_solar_kw=unallocated_solar,
        optimization_status="OPTIMAL (DEMO)",
        is_demo=True,
        explanatory_note="Prototype demo response — PuLP fair solar allocation optimization model is not yet connected.",
    )
