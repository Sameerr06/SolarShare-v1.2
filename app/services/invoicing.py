"""Invoicing service — idempotent invoice generation and retrieval."""

import calendar
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.invoice import Invoice, InvoiceLineItem
from app.models.tariff import Tariff
from app.models.tenant import Tenant
from app.models.estate import Estate
from app.schemas.billing import BillingTenantSummary
from app.services.billing import get_billing_rows_for_invoice


SOLAR_RATE = 5.00  # ₹/kWh


def ensure_invoices_for_month(
    db: Session,
    month: str,
    tenant_id: Optional[int] = None,
) -> List[Invoice]:
    """
    Generate or retrieve invoices for all tenants (or one tenant) for the given month.
    Idempotent: re-running for the same month+tenant does not create duplicates.
    Returns the list of invoices created or found.
    """
    if not _valid_month(month):
        raise ValueError(f"Invalid month format: {month}. Expected YYYY-MM")

    rows = get_billing_rows_for_invoice(month, tenant_id)
    invoices: List[Invoice] = []

    for row in rows:
        invoice = _upsert_invoice(db, month, row)
        invoices.append(invoice)

    db.commit()
    return invoices


def get_invoice_or_none(db: Session, invoice_id: int) -> Optional[Invoice]:
    return db.get(Invoice, invoice_id)


def get_invoices_for_month(
    db: Session,
    month: str,
    tenant_id: Optional[int] = None,
) -> List[Invoice]:
    query = db.query(Invoice).filter(Invoice.billing_period == month)
    if tenant_id is not None:
        query = query.filter(Invoice.tenant_id == tenant_id)
    return query.order_by(Invoice.tenant_id).all()


def _upsert_invoice(db: Session, month: str, row: BillingTenantSummary) -> Invoice:
    """Create or update an invoice for a tenant+month. Line items are rebuilt each time."""
    existing = (
        db.query(Invoice)
        .filter(Invoice.tenant_id == row.tenant_id, Invoice.billing_period == month)
        .first()
    )

    # Resolve display context
    tenant = db.get(Tenant, row.tenant_id)
    tenant_name = tenant.name if tenant else row.tenant_name
    estate = None
    if tenant and tenant.estate_id:
        estate = db.get(Estate, tenant.estate_id)
    if not estate:
        estate = db.query(Estate).first()
    estate_name = estate.name if estate else "SolarShare Industrial Estate"

    # Tariff for source reference
    tariff = db.query(Tariff).order_by(Tariff.effective_from.desc()).first()

    invoice_number = f"SS-{month}-T{row.tenant_id:04d}"
    issue_date = datetime(int(month[:4]), int(month[5:]), 1, tzinfo=timezone.utc)
    # Due date = 15th of following month (or last day if month has fewer days)
    year, m = int(month[:4]), int(month[5:])
    if m == 12:
        due_year, due_month = year + 1, 1
    else:
        due_year, due_month = year, m + 1
    last_day = calendar.monthrange(due_year, due_month)[1]
    due_day = min(15, last_day)
    due_date = datetime(due_year, due_month, due_day, tzinfo=timezone.utc)

    if existing:
        # Update totals and line items
        existing.invoice_number = invoice_number
        existing.issue_date = issue_date
        existing.due_date = due_date
        existing.status = "ISSUED"
        existing.total_consumption_kwh = row.total_consumption_kwh
        existing.solar_consumed_kwh = row.solar_consumed_kwh
        existing.grid_consumed_kwh = row.grid_consumed_kwh
        existing.solar_cost_inr = row.solar_cost_inr
        existing.grid_cost_inr = row.grid_cost_inr
        existing.total_bill_inr = row.total_bill_inr
        existing.savings_inr = row.savings_inr
        # Rebuild line items (delete old, insert new)
        existing.line_items.clear()
        db.flush()
        _add_line_items(db, existing, row, tariff)
        return existing

    invoice = Invoice(
        invoice_number=invoice_number,
        tenant_id=row.tenant_id,
        billing_period=month,
        issue_date=issue_date,
        due_date=due_date,
        status="ISSUED",
        total_consumption_kwh=row.total_consumption_kwh,
        solar_consumed_kwh=row.solar_consumed_kwh,
        grid_consumed_kwh=row.grid_consumed_kwh,
        solar_cost_inr=row.solar_cost_inr,
        grid_cost_inr=row.grid_cost_inr,
        total_bill_inr=row.total_bill_inr,
        savings_inr=row.savings_inr,
    )
    db.add(invoice)
    db.flush()
    _add_line_items(db, invoice, row, tariff)
    return invoice


def _add_line_items(
    db: Session,
    invoice: Invoice,
    row: BillingTenantSummary,
    tariff: Optional[Tariff],
) -> None:
    """Build line items for an invoice from billing row data."""
    # Solar line
    db.add(
        InvoiceLineItem(
            invoice_id=invoice.id,
            description="Solar energy consumed (shared PV)",
            category="SOLAR",
            quantity_kwh=row.solar_consumed_kwh,
            rate_inr_per_kwh=SOLAR_RATE,
            amount_inr=row.solar_cost_inr,
        )
    )

    # Grid line — rate is derived from row's grid_cost / grid_kwh
    grid_rate = row.grid_cost_inr / row.grid_consumed_kwh if row.grid_consumed_kwh > 0 else 0.0
    db.add(
        InvoiceLineItem(
            invoice_id=invoice.id,
            description="Grid energy consumed (ToU tariff)",
            category="GRID",
            quantity_kwh=row.grid_consumed_kwh,
            rate_inr_per_kwh=grid_rate,
            amount_inr=row.grid_cost_inr,
        )
    )

    # Tax line — compute from active tariff's electricity_tax_pct (or demo 5%)
    tax_pct = 5.0
    if tariff and tariff.periods:
        # Weighted average tax across periods (all demo periods use 5%)
        tax_pct = sum(p.electricity_tax_pct for p in tariff.periods) / len(tariff.periods)

    taxable_amount = row.solar_cost_inr + row.grid_cost_inr
    tax_amount = taxable_amount * (tax_pct / 100.0)
    db.add(
        InvoiceLineItem(
            invoice_id=invoice.id,
            description=f"Electricity tax @ {tax_pct:.1f}%",
            category="TAX",
            quantity_kwh=0.0,
            rate_inr_per_kwh=tax_pct,
            amount_inr=tax_amount,
        )
    )

    # Total payable line
    total_payable = row.solar_cost_inr + row.grid_cost_inr + tax_amount
    db.add(
        InvoiceLineItem(
            invoice_id=invoice.id,
            description="Total payable (solar + grid + tax)",
            category="TOTAL",
            quantity_kwh=row.total_consumption_kwh,
            rate_inr_per_kwh=total_payable / row.total_consumption_kwh if row.total_consumption_kwh > 0 else 0.0,
            amount_inr=total_payable,
        )
    )

    # Savings note line (category NOTE — the renderer formats description + amount)
    db.add(
        InvoiceLineItem(
            invoice_id=invoice.id,
            description="Savings vs 100% grid tariff",
            category="NOTE",
            quantity_kwh=0.0,
            rate_inr_per_kwh=0.0,
            amount_inr=row.savings_inr,
        )
    )


def _valid_month(month: str) -> bool:
    try:
        datetime.strptime(month, "%Y-%m")
        return True
    except ValueError:
        return False