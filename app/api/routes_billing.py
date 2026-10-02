"""API routes for Tamil Nadu ToU electricity tariff and tenant billing summary."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role, verify_tenant_access
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.billing import BillingSummaryResponse, TariffRead
from app.services.billing import get_monthly_billing_summary, get_tariff_read

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get(
    "/tariffs",
    response_model=TariffRead,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
def get_tariffs(db: Session = Depends(get_db)) -> TariffRead:
    return get_tariff_read(db)


@router.get("/summary", response_model=BillingSummaryResponse)
def get_billing_summary(
    month: str = Query("2026-08", description="Billing period format YYYY-MM"),
    tenant_id: Optional[int] = Query(None, description="Optional tenant_id filter"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BillingSummaryResponse:
    """
    Billing summary for a period.

    ADMIN callers may filter by `tenant_id` (or omit it for the whole estate).
    A TENANT caller is always pinned to their own `tenant_id`, whatever they
    pass — `verify_tenant_access` rejects a mismatching filter with 403, and a
    tenant row with no `tenant_id` mapped can never fall back to the
    estate-wide summary.
    """
    if current_user.role == UserRole.TENANT:
        if current_user.tenant_id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: this account is not linked to a tenant.",
            )
        if tenant_id is not None:
            verify_tenant_access(tenant_id, current_user)
        effective_tenant_id = current_user.tenant_id
        tenant_row = db.get(Tenant, effective_tenant_id)
        return get_monthly_billing_summary(
            db,
            month,
            effective_tenant_id,
            # Strict: an id the demo table does not know must return nothing rather
            # than the whole estate's bills.
            strict_tenant_filter=True,
            tenant_name=tenant_row.name if tenant_row else None,
        )

    return get_monthly_billing_summary(db, month, tenant_id)