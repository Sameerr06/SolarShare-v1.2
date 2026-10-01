"""Billing summary service — shared logic for /billing/summary and invoice generation."""

from datetime import datetime, time, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.tariff import Tariff
from app.schemas.billing import BillingSummaryResponse, BillingTenantSummary, TariffPeriodRead, TariffRead


# The authoritative demo tenant billing data used by both the summary endpoint
# and the invoice generator. Keep this in sync with the Tariff rates if they change.
DEMO_TENANTS = [
    {
        "tenant_id": 1,
        "tenant_name": "Textile Manufacturing Unit",
        "total_consumption_kwh": 43200.0,
        "solar_consumed_kwh": 21600.0,
        "grid_consumed_kwh": 21600.0,
        "solar_cost_inr": 108000.0,
        "grid_cost_inr": 183600.0,
        "total_bill_inr": 291600.0,
        "savings_inr": 75600.0,
    },
    {
        "tenant_id": 2,
        "tenant_name": "Food Processing Facility",
        "total_consumption_kwh": 28800.0,
        "solar_consumed_kwh": 14400.0,
        "grid_consumed_kwh": 14400.0,
        "solar_cost_inr": 72000.0,
        "grid_cost_inr": 122400.0,
        "total_bill_inr": 194400.0,
        "savings_inr": 50400.0,
    },
    {
        "tenant_id": 3,
        "tenant_name": "Electronics Assembly",
        "total_consumption_kwh": 21600.0,
        "solar_consumed_kwh": 10800.0,
        "grid_consumed_kwh": 10800.0,
        "solar_cost_inr": 54000.0,
        "grid_cost_inr": 91800.0,
        "total_bill_inr": 145800.0,
        "savings_inr": 37800.0,
    },
    {
        "tenant_id": 4,
        "tenant_name": "Packaging & Plastics Unit",
        "total_consumption_kwh": 14400.0,
        "solar_consumed_kwh": 7200.0,
        "grid_consumed_kwh": 7200.0,
        "solar_cost_inr": 36000.0,
        "grid_cost_inr": 61200.0,
        "total_bill_inr": 97200.0,
        "savings_inr": 25200.0,
    },
    {
        "tenant_id": 5,
        "tenant_name": "General Engineering Works",
        "total_consumption_kwh": 12000.0,
        "solar_consumed_kwh": 6000.0,
        "grid_consumed_kwh": 6000.0,
        "solar_cost_inr": 30000.0,
        "grid_cost_inr": 51000.0,
        "total_bill_inr": 81000.0,
        "savings_inr": 21000.0,
    },
    {
        "tenant_id": 6,
        "tenant_name": "Precision Tooling Workshop",
        "total_consumption_kwh": 18000.0,
        "solar_consumed_kwh": 9000.0,
        "grid_consumed_kwh": 9000.0,
        "solar_cost_inr": 45000.0,
        "grid_cost_inr": 76500.0,
        "total_bill_inr": 121500.0,
        "savings_inr": 31500.0,
    },
]


def get_monthly_billing_summary(
    db: Session,
    month: str,
    tenant_id: Optional[int] = None,
) -> BillingSummaryResponse:
    """
    Return the billing summary for a given month, optionally filtered to one tenant.
    This is the single source of truth for billing numbers used by both the
    summary endpoint and the invoice generator.
    """
    # Validate month format
    if not _valid_month(month):
        month = "2026-08"

    tenants_demo = [BillingTenantSummary(**t) for t in DEMO_TENANTS]

    if tenant_id is not None:
        filtered = [t for t in tenants_demo if t.tenant_id == tenant_id]
        if filtered:
            tenants_demo = filtered

    total_consumption = sum(t.total_consumption_kwh for t in tenants_demo)
    total_solar = sum(t.solar_consumed_kwh for t in tenants_demo)
    total_grid = sum(t.grid_consumed_kwh for t in tenants_demo)
    total_solar_cost = sum(t.solar_cost_inr for t in tenants_demo)
    total_grid_cost = sum(t.grid_cost_inr for t in tenants_demo)
    total_savings = sum(t.savings_inr for t in tenants_demo)

    return BillingSummaryResponse(
        billing_period=month,
        total_estate_consumption_kwh=total_consumption,
        total_solar_consumed_kwh=total_solar,
        total_grid_consumed_kwh=total_grid,
        total_solar_cost_inr=total_solar_cost,
        total_grid_cost_inr=total_grid_cost,
        total_savings_inr=total_savings,
        tenants=tenants_demo,
        is_demo=True,
        explanatory_note="Tamil Nadu ToU billing summary response with tenant-scoped calculation support.",
    )


def get_billing_rows_for_invoice(
    month: str,
    tenant_id: Optional[int] = None,
) -> List[BillingTenantSummary]:
    """
    Return the raw per-tenant rows used for invoice generation (without the
    aggregated estate totals). Useful for the invoicing service.
    """
    tenants_demo = [BillingTenantSummary(**t) for t in DEMO_TENANTS]
    if tenant_id is not None:
        # Strict: unknown tenant ids return no rows (the summary endpoint keeps
        # its lenient "fall back to all" behaviour separately).
        tenants_demo = [t for t in tenants_demo if t.tenant_id == tenant_id]
    return tenants_demo


def get_tariff_read(db: Session) -> TariffRead:
    """Return the active tariff as a TariffRead, or a demo fallback."""
    tariff = db.query(Tariff).order_by(Tariff.effective_from.desc()).first()

    if tariff is not None:
        period_reads = [
            TariffPeriodRead(
                id=p.id,
                period_name=p.period_name.value if hasattr(p.period_name, "value") else str(p.period_name),
                start_time=p.start_time.strftime("%H:%M:%S") if isinstance(p.start_time, time) else str(p.start_time),
                end_time=p.end_time.strftime("%H:%M:%S") if isinstance(p.end_time, time) else str(p.end_time),
                base_energy_charge_inr_per_kwh=p.base_energy_charge_inr_per_kwh,
                electricity_tax_pct=p.electricity_tax_pct,
                effective_rate_inr_per_kwh=p.effective_rate_inr_per_kwh,
            )
            for p in tariff.periods
        ]

        return TariffRead(
            id=tariff.id,
            name=tariff.name,
            category=tariff.category,
            effective_from=tariff.effective_from,
            source=tariff.source,
            source_reference=tariff.source_reference,
            label=tariff.label,
            periods=period_reads,
            is_demo=False,
            explanatory_note="Real Tamil Nadu ToU industrial tariff structure stored in database.",
        )

    # Demo fallback
    demo_periods = [
        TariffPeriodRead(
            id=1,
            period_name="PEAK_MORNING",
            start_time="06:00:00",
            end_time="10:00:00",
            base_energy_charge_inr_per_kwh=7.50,
            electricity_tax_pct=5.0,
            effective_rate_inr_per_kwh=9.375,
        ),
        TariffPeriodRead(
            id=2,
            period_name="NORMAL_DAY",
            start_time="10:00:00",
            end_time="18:00:00",
            base_energy_charge_inr_per_kwh=7.50,
            electricity_tax_pct=5.0,
            effective_rate_inr_per_kwh=7.875,
        ),
        TariffPeriodRead(
            id=3,
            period_name="PEAK_EVENING",
            start_time="18:00:00",
            end_time="22:00:00",
            base_energy_charge_inr_per_kwh=7.50,
            electricity_tax_pct=5.0,
            effective_rate_inr_per_kwh=9.375,
        ),
        TariffPeriodRead(
            id=4,
            period_name="OFF_PEAK_NIGHT",
            start_time="22:00:00",
            end_time="06:00:00",
            base_energy_charge_inr_per_kwh=7.50,
            electricity_tax_pct=5.0,
            effective_rate_inr_per_kwh=7.481,
        ),
    ]

    return TariffRead(
        id=1,
        name="Tamil Nadu HT Industrial Tariff (HT Category III)",
        category="INDUSTRIAL",
        effective_from=datetime(2025, 4, 1, tzinfo=timezone.utc),
        source="TNERC Tariff Order FY 2025-26",
        source_reference="TNERC Order No. 7 of 2024 (ToU Surcharge/Rebate provisions)",
        label="Tamil Nadu FY 2025-26 prototype tariff configuration",
        periods=demo_periods,
        is_demo=True,
        explanatory_note="Prototype Tamil Nadu ToU tariff structure assumption (unseeded DB fallback).",
    )


def _valid_month(month: str) -> bool:
    try:
        datetime.strptime(month, "%Y-%m")
        return True
    except ValueError:
        return False