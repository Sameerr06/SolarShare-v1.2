"""API routes for invoice listing, generation and PDF download.

Access model:
- ADMIN: sees every tenant's invoices, may download any individual invoice
  and the consolidated estate summary.
- TENANT: scoped to their own tenant_id only; passing another tenant's id
  raises 403 via `verify_tenant_access`.
All endpoints require authentication — invoices carry per-tenant financial data.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_role, verify_tenant_access
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.estate import Estate
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.invoice import InvoiceGenerateRequest, InvoiceListResponse, InvoiceRead
from app.services.billing import DEMO_TENANTS, get_tariff_read
from app.services.invoicing import ensure_invoices_for_month, get_invoices_for_month
from app.services.pdf_invoice import render_estate_summary_pdf, render_invoice_pdf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing/invoices", tags=["billing-invoices"])

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


def _display_names(db: Session) -> dict:
    """tenant_id -> display name (DB rows win over demo fallback names)."""
    names = {t["tenant_id"]: t["tenant_name"] for t in DEMO_TENANTS}
    for tenant in db.query(Tenant).all():
        names[tenant.id] = tenant.name
    return names


def _estate_name(db: Session) -> str:
    estate = db.query(Estate).first()
    return estate.name if estate else "SolarShare Industrial Estate"


def _to_read(db: Session, invoice, tenant_name: Optional[str] = None) -> InvoiceRead:
    names = _display_names(db) if tenant_name is None else None
    display = tenant_name if tenant_name is not None else names.get(invoice.tenant_id, f"Tenant #{invoice.tenant_id}")
    return InvoiceRead(
        id=invoice.id,
        invoice_number=invoice.invoice_number,
        tenant_id=invoice.tenant_id,
        tenant_name=display,
        billing_period=invoice.billing_period,
        issue_date=invoice.issue_date,
        due_date=invoice.due_date,
        status=invoice.status,
        total_consumption_kwh=invoice.total_consumption_kwh,
        solar_consumed_kwh=invoice.solar_consumed_kwh,
        grid_consumed_kwh=invoice.grid_consumed_kwh,
        solar_cost_inr=invoice.solar_cost_inr,
        grid_cost_inr=invoice.grid_cost_inr,
        total_bill_inr=invoice.total_bill_inr,
        savings_inr=invoice.savings_inr,
        line_items=[li for li in invoice.line_items],
        pdf_url=(
            f"/api/billing/invoices/pdf?month={invoice.billing_period}"
            f"&tenant_id={invoice.tenant_id}"
        ),
    )


@router.get("", response_model=InvoiceListResponse)
def list_invoices(
    month: str = Query("2026-08", pattern=MONTH_PATTERN, description="Billing period YYYY-MM"),
    tenant_id: Optional[int] = Query(
        None,
        description="Optional tenant_id filter. ADMIN may filter; a TENANT may only pass their own id.",
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> InvoiceListResponse:
    """
    List invoices for a month. ADMIN sees all (optionally filtered by `tenant_id`);
    TENANT sees only their own, and asking for anyone else's id is a 403 rather
    than a silently ignored filter.
    """
    effective_tenant_id: Optional[int] = tenant_id
    if current_user.role == UserRole.TENANT:
        if current_user.tenant_id is None:
            raise HTTPException(status_code=400, detail="User has no tenant assigned.")
        if tenant_id is not None:
            verify_tenant_access(tenant_id, current_user)
        effective_tenant_id = current_user.tenant_id

    invoices = get_invoices_for_month(db, month, effective_tenant_id)
    return InvoiceListResponse(
        billing_period=month,
        invoices=[_to_read(db, inv) for inv in invoices],
        count=len(invoices),
    )


@router.post("/generate", response_model=InvoiceListResponse)
def generate_invoices(
    payload: InvoiceGenerateRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.ADMIN)),
) -> InvoiceListResponse:
    """Create (or refresh) invoices for every tenant in the given month. Idempotent."""
    invoices = ensure_invoices_for_month(db, payload.month, None)
    return InvoiceListResponse(
        billing_period=payload.month,
        invoices=[_to_read(db, inv) for inv in invoices],
        count=len(invoices),
    )


@router.get("/pdf")
def download_invoice_pdf(
    month: str = Query("2026-08", pattern=MONTH_PATTERN, description="Billing period YYYY-MM"),
    tenant_id: Optional[int] = Query(None, description="Tenant id (admin only; tenants are forced to their own)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    """Download a single tenant's invoice PDF.

    - TENANT: always their own invoice; requesting another tenant's id -> 403.
    - ADMIN: must supply tenant_id.
    The invoice is generated on demand if it does not exist yet.
    """
    if current_user.role == UserRole.TENANT:
        if tenant_id is not None:
            verify_tenant_access(tenant_id, current_user)  # raises 403 on mismatch
        if current_user.tenant_id is None:
            raise HTTPException(status_code=400, detail="User has no tenant assigned.")
        effective_tenant_id = current_user.tenant_id
    else:
        if tenant_id is None:
            raise HTTPException(
                status_code=400,
                detail="tenant_id is required to download an invoice as admin.",
            )
        effective_tenant_id = tenant_id

    invoices = ensure_invoices_for_month(db, month, effective_tenant_id)
    if not invoices:
        raise HTTPException(
            status_code=404,
            detail=f"No billing data for tenant {effective_tenant_id} in period {month}.",
        )
    invoice = invoices[0]

    names = _display_names(db)
    pdf_bytes = render_invoice_pdf(
        invoice,
        tenant_name=names.get(invoice.tenant_id, f"Tenant #{invoice.tenant_id}"),
        estate_name=_estate_name(db),
        tariff=get_tariff_read(db),
    )
    filename = f"{invoice.invoice_number}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/estate/summary.pdf")
def download_estate_summary_pdf(
    month: str = Query("2026-08", pattern=MONTH_PATTERN, description="Billing period YYYY-MM"),
    db: Session = Depends(get_db),
    _: User = Depends(require_role(UserRole.ADMIN)),
) -> Response:
    """Download the consolidated estate-wide billing summary PDF for a month (ADMIN only)."""
    invoices = ensure_invoices_for_month(db, month, None)
    if not invoices:
        raise HTTPException(status_code=404, detail=f"No invoices available for period {month}.")

    pdf_bytes = render_estate_summary_pdf(
        month,
        invoices,
        estate_name=_estate_name(db),
        tenant_names=_display_names(db),
    )
    filename = f"SolarShare-Estate-Billing-Summary-{month}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )