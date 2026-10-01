"""API routes for Tamil Nadu ToU electricity tariff and tenant billing summary."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_optional_current_user, verify_tenant_access
from app.db.session import get_db
from app.models.user import User
from app.schemas.billing import BillingSummaryResponse, TariffRead
from app.services.billing import get_monthly_billing_summary, get_tariff_read

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.get("/tariffs", response_model=TariffRead)
def get_tariffs(db: Session = Depends(get_db)) -> TariffRead:
    return get_tariff_read(db)


@router.get("/summary", response_model=BillingSummaryResponse)
def get_billing_summary(
    month: str = Query("2026-08", description="Billing period format YYYY-MM"),
    tenant_id: Optional[int] = Query(None, description="Optional tenant_id filter"),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
) -> BillingSummaryResponse:
    if tenant_id is not None:
        verify_tenant_access(tenant_id, current_user)

    effective_tenant_id = tenant_id
    if current_user and current_user.role.value == "TENANT":
        effective_tenant_id = current_user.tenant_id

    return get_monthly_billing_summary(db, month, effective_tenant_id)