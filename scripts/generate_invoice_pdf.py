"""
Invoice PDF generation CLI (admin-side tool).

Generates invoices for a billing month and writes PDFs to disk without going
through the HTTP API — useful for bulk runs, CI checks, or verifying the
renderer in isolation.

Usage (from the project root, venv activated):
    python scripts/generate_invoice_pdf.py --month 2026-08 --estate
    python scripts/generate_invoice_pdf.py --month 2026-08 --tenant-id 3 --out ./invoices
    python scripts/generate_invoice_pdf.py --month 2026-08            # all tenants

Outputs:
    <out>/SS-<month>-T<id>.pdf              per-tenant invoices
    <out>/SolarShare-Estate-Billing-Summary-<month>.pdf   (--estate)
"""

import argparse
import os
import sys

# Running a script puts its own directory — `scripts/` — on sys.path, not the
# working directory, so `import app` would otherwise fail.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal  # noqa: E402
from app.db.init_db import init_db  # noqa: E402
from app.models.estate import Estate  # noqa: E402
from app.models.tenant import Tenant  # noqa: E402
from app.services.billing import DEMO_TENANTS, get_tariff_read  # noqa: E402
from app.services.invoicing import ensure_invoices_for_month  # noqa: E402
from app.services.pdf_invoice import render_estate_summary_pdf, render_invoice_pdf  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate SolarShare invoice PDFs.")
    parser.add_argument("--month", required=True, help="Billing period in YYYY-MM format")
    parser.add_argument("--tenant-id", type=int, default=None,
                        help="Generate only this tenant's invoice (default: all tenants)")
    parser.add_argument("--estate", action="store_true",
                        help="Also write the consolidated estate summary PDF")
    parser.add_argument("--out", default=".", help="Output directory (default: current dir)")
    args = parser.parse_args()

    init_db()  # ensure schema exists on the configured DATABASE_URL
    os.makedirs(args.out, exist_ok=True)

    db = SessionLocal()
    try:
        invoices = ensure_invoices_for_month(db, args.month, args.tenant_id)
        if not invoices:
            print(f"No billing data found for month={args.month}"
                  + (f", tenant_id={args.tenant_id}" if args.tenant_id else "")
                  + ".")
            return 1

        names = {t["tenant_id"]: t["tenant_name"] for t in DEMO_TENANTS}
        for tenant in db.query(Tenant).all():
            names[tenant.id] = tenant.name
        estate = db.query(Estate).first()
        estate_name = estate.name if estate else "SolarShare Industrial Estate"
        tariff = get_tariff_read(db)

        written = []
        for invoice in invoices:
            pdf = render_invoice_pdf(
                invoice,
                tenant_name=names.get(invoice.tenant_id, f"Tenant #{invoice.tenant_id}"),
                estate_name=estate_name,
                tariff=tariff,
            )
            path = os.path.join(args.out, f"{invoice.invoice_number}.pdf")
            with open(path, "wb") as fh:
                fh.write(pdf)
            written.append(path)

        if args.estate:
            pdf = render_estate_summary_pdf(
                args.month,
                invoices,
                estate_name=estate_name,
                tenant_names=names,
            )
            path = os.path.join(args.out, f"SolarShare-Estate-Billing-Summary-{args.month}.pdf")
            with open(path, "wb") as fh:
                fh.write(pdf)
            written.append(path)

        for path in written:
            size = os.path.getsize(path)
            print(f"wrote {path} ({size:,} bytes)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())