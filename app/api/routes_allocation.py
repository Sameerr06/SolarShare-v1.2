"""API routes for fair solar energy allocation optimization (PuLP model integration scope)."""

import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.allocation import AllocationCurrentResponse, TenantAllocationItem

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/allocation", tags=["allocation"])


@router.get("/current", response_model=AllocationCurrentResponse)
def get_current_allocation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AllocationCurrentResponse:
    """
    Current fair-allocation snapshot for the estate.

    ADMIN callers get every tenant's row. A TENANT caller gets ONLY their own
    row — the estate-wide split (who demanded how much, who got how much solar)
    is exactly the cross-tenant information that must not leave the server.
    """
    tenants = db.query(Tenant).order_by(Tenant.id).all()
    now_str = datetime.now().strftime("%Y-%m-%dT%H:00:00")

    total_solar = 320.0  # kW current solar generation
    total_demand = 0.0

    # Demand/share per position in the estate. These are attached to the *real*
    # Tenant rows rather than to hardcoded ids 1..N: a tenant created later (or
    # on a second estate) must still be able to see their own row, otherwise the
    # TENANT filter below silently matches nothing and the caller gets an empty
    # split. Tenants beyond this list fall back to an equal share.
    demo_profiles = [
        (180.0, 0.35),
        (120.0, 0.25),
        (90.0, 0.18),
        (60.0, 0.12),
        (50.0, 0.10),
    ]
    fallback_demand = 40.0
    fallback_share = 1.0 / len(tenants) if tenants else 0.0

    allocations: List[TenantAllocationItem] = []

    for i, tenant in enumerate(tenants):
        demand_kw, share = (
            demo_profiles[i] if i < len(demo_profiles) else (fallback_demand, fallback_share)
        )
        total_demand += demand_kw
        solar_alloc = round(min(demand_kw, total_solar * share), 2)
        battery_power = round(min(demand_kw - solar_alloc, 15.0), 2)
        grid_power = round(max(0.0, demand_kw - solar_alloc - battery_power), 2)

        allocations.append(
            TenantAllocationItem(
                tenant_id=tenant.id,
                tenant_name=tenant.name,
                demanded_kw=demand_kw,
                allocated_solar_kw=solar_alloc,
                battery_power_kw=battery_power,
                grid_power_kw=grid_power,
                fairness_share_pct=round(share * 100, 1),
            )
        )

    visible_allocations = allocations
    if current_user.role == UserRole.TENANT:
        visible_allocations = [
            a for a in allocations if a.tenant_id == current_user.tenant_id
        ]

    sum_solar_allocated = sum(a.allocated_solar_kw for a in visible_allocations)
    unallocated_solar = max(0.0, round(total_solar - sum_solar_allocated, 2))

    return AllocationCurrentResponse(
        timestamp=now_str,
        total_solar_available_kw=total_solar,
        total_estate_demand_kw=total_demand,
        allocations=visible_allocations,
        unallocated_solar_kw=unallocated_solar,
        optimization_status="OPTIMAL (DEMO)",
        is_demo=True,
        explanatory_note="Prototype demo response — PuLP fair solar allocation optimization model is not yet connected.",
    )
