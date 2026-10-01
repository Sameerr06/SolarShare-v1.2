# PDF Invoice Generation Tool (Admin + Tenant)

## Context

SolarShare has a working auth/role system and a **demo** billing endpoint (`GET /api/billing/summary`
in `app/api/routes_billing.py:110`) that returns hardcoded per-tenant numbers, but **no Invoice model,
no invoicing service, no PDF code and no PDF dependency** exist anywhere in the repo (confirmed by
repo-wide grep). Billing data today only lives in inline demo literals inside the router.

Goal: a real invoice PDF generation tool where
- **ADMIN** can list/generate invoices for every tenant and download either an individual tenant
  invoice or a consolidated estate summary PDF for a month;
- **TENANT** can only ever see/download **their own** invoice.

Decisions confirmed with the user:
1. **Persist invoices** in the DB (`Invoice` + line items), generated on demand, idempotent.
2. **reportlab** as the PDF library (pure Python, already anticipated by the `requirements.txt:2`
   comment, installs cleanly on this Windows/Python 3.14 box — verified with `pip --dry-run`).
3. **Wire the React frontend** (admin Billing page + tenant portal).
4. **Admin gets both** per-tenant invoices and an estate-wide summary PDF.

## Current-state facts the implementation must respect

- Router registration: `app/main.py` — one `app.include_router(x_router, prefix="/api")` line per
  domain; billing router registered at `main.py:95`.
- Role gating lives in `app/api/deps.py`: `require_role(UserRole.ADMIN)` (403, keeps 401 for
  anonymous) and `verify_tenant_access(tenant_id, current_user)` (403 "Access denied: …").
- `/billing/summary` convention: `get_optional_current_user` + force
  `effective_tenant_id = current_user.tenant_id` when role is TENANT.
- Models must be imported in `app/models/base.py` or they will **not** exist in the test schema
  (`tests/conftest.py:18` relies on that import).
- Tests: in-memory SQLite, per-file `_admin_token` / `_auth` helpers (see `tests/test_auth.py`
  role matrix, `tests/test_estate_routes.py` seeding helpers).
- No binary/file responses exist anywhere yet — the PDF endpoints will be the first.
- Frontend: `src/api/client.ts` (axios + bearer interceptor, no Blob code yet),
  `src/types/api.ts` for types, `src/pages/BillingPage.tsx` (admin),
  `src/pages/TenantPortalPage.tsx` (tenant), role guards already in `src/App.tsx`.

## Implementation steps

### 1. Dependency

- `pip install reportlab==4.2.5`
- Add to `requirements.txt` (Docker / py3.11 pin) **and** `requirements-dev.txt` (local py3.14).

### 2. Extract the billing summary into a service (refactor, no behaviour change)

Move the inline demo logic out of the router so both the router and the invoicing service use one
source of truth:

- New `app/services/billing.py`:
  `get_monthly_billing_summary(db, month: str, tenant_id: int | None) -> BillingSummaryResponse`
  — body moved verbatim from `routes_billing.py:110-216` (identical demo numbers, identical
  `is_demo` / `explanatory_note`), plus expose the raw per-tenant rows for the invoice builder.
- `app/api/routes_billing.py` `get_billing_summary` becomes a thin wrapper: access checks stay in
  the route (`verify_tenant_access` + TENANT forcing), then call the service.
  Existing `tests/test_dashboard_routes.py::test_billing_routes` must stay green (response shape
  unchanged).

### 3. New ORM models — `app/models/invoice.py`

Both `Base, TimestampMixin` (mixins from `app/models/mixins.py`).

```python
class Invoice(Base, TimestampMixin):            # table "invoices"
    id: int                     # PK
    invoice_number: str         # String(32), unique, e.g. "SS-2026-08-T0001"
    tenant_id: int              # FK "tenants.id", nullable=False, index
    billing_period: str         # String(7) "YYYY-MM", index
    issue_date / due_date: datetime
    status: str                 # String(16), default "ISSUED"
    total_consumption_kwh / solar_consumed_kwh / grid_consumed_kwh: float
    solar_cost_inr / grid_cost_inr / total_bill_inr / savings_inr: float
    line_items: List["InvoiceLineItem"]         # relationship, cascade delete-orphan
    __table_args__ = (UniqueConstraint("tenant_id", "billing_period"),)

class InvoiceLineItem(Base, TimestampMixin):    # table "invoice_line_items"
    id: int
    invoice_id: int             # FK "invoices.id", index, ondelete CASCADE
    description: str            # String(255)
    category: str               # String(32): SOLAR | GRID | TAX | TOTAL | NOTE
    quantity_kwh: float
    rate_inr_per_kwh: float
    amount_inr: float
```

- Register both in `app/models/base.py` (import + `__all__`), per that file's own instruction.
- The `tenant_id` FK assumes a real `Tenant` row; where the demo summary uses tenant ids with no
  matching row, the builder keeps the summary's `tenant_name` as display text (see step 4) and
  still persists the invoice against the id. Tenant lookup failures must never crash generation.

### 4. Invoicing service — `app/services/invoicing.py`

- `ensure_invoices_for_month(db, month, tenant_id=None) -> list[Invoice]`
  - pulls rows from `get_monthly_billing_summary(...)` (or a raw-row variant),
  - for each row: **upsert** on `(tenant_id, billing_period)` — reuse existing invoice + line
    items instead of duplicating (idempotent; re-running never doubles rows),
  - builds line items: `Solar energy consumed @ ₹5.00/kWh`, `Grid energy consumed (ToU)`,
    computed `Electricity tax @ 5%` (from the active `TariffPeriod.electricity_tax_pct` when a
    `Tariff` exists, else the demo 5%), plus a `Total payable` line and a `Savings vs 100% grid`
    note line,
  - `invoice_number = f"SS-{month}-T{tenant_id:04d}"` (stable per tenant+month, so downloads are
    reproducible),
  - `issue_date = first day of month`, `due_date = +15 days`,
  - returns the invoices it created/updated.
- `get_invoice_or_none(db, invoice_id) -> Invoice | None`
- Helper to resolve display context (tenant name/estate name) with safe fallbacks.

### 5. PDF renderer — `app/services/pdf_invoice.py` (pure, no DB writes)

reportlab Platypus (`SimpleDocTemplate` + `Paragraph`/`Table`/`Spacer`) writing to a
`io.BytesIO`, returning `bytes`. Two entry points:

- `render_invoice_pdf(invoice, *, tenant_name, estate_name, tariff) -> bytes`
  Sections: SolarShare header band (drawn with reportlab primitives — **no logo file exists**, do
  not invent one) · invoice number, billing period, issue/due dates, status · **Bill To** block
  (tenant) · line-item table (description | kWh | rate ₹/kWh | amount ₹) · sub-total block
  (solar + grid + tax = total payable) · savings callout · ToU tariff source reference
  (`Tariff.source` / `source_reference`, or the demo fallback text) · footer disclaimer carrying
  the same prototype/demo disclosure the API uses (`DemoResponseMixin` note).
- `render_estate_summary_pdf(month, invoices, totals) -> bytes`
  Header + period, estate-wide totals, then one row per tenant invoice (invoice #, tenant, kWh,
  solar ₹, grid ₹, total ₹, savings ₹) + grand-total row + same footer disclaimer.

Formatting helpers: `₹` thousands separators, 2-decimal currency, `kWh` with separators.
Use Helvetica (built-in) — no font files to ship.

### 6. Schemas — new `app/schemas/invoice.py`

Matches the one-file-per-domain convention:
`InvoiceLineRead`, `InvoiceRead` (incl. `invoice_number`, `billing_period`, totals, `tenant_id`,
`tenant_name`, `line_items`, `pdf_url`), `InvoiceListResponse` (month + `invoices` list),
`InvoiceGenerateRequest` (`month: str`). Admin list carries all tenants; tenant list carries one.

### 7. API — new `app/api/routes_invoices.py`, registered in `app/main.py`

`router = APIRouter(prefix="/billing/invoices", tags=["billing-invoices"])`, then one
`app.include_router(invoices_router, prefix="/api")` line next to `billing_router` (`main.py:95`).

| Method | Path | Access | Behaviour |
|---|---|---|---|
| GET | `/api/billing/invoices?month=YYYY-MM` | ADMIN or TENANT (auth required) | admin → all invoices for month; tenant → forced to own `tenant_id` |
| POST | `/api/billing/invoices/generate` | `require_role(ADMIN)` | body `{month}` → `ensure_invoices_for_month` → `InvoiceListResponse` |
| GET | `/api/billing/invoices/pdf?month=&tenant_id=` | ADMIN or TENANT | TENANT: `tenant_id` forced to own (and 403 if they pass another id via `verify_tenant_access`); ADMIN: `tenant_id` required (400 if absent). get-or-generate, then stream PDF |
| GET | `/api/billing/invoices/estate/summary.pdf?month=` | `require_role(ADMIN)` | consolidated estate PDF for the month |

- All four require authentication (`get_current_user`) — unlike `/billing/summary`, invoices are
  per-tenant financial data and must not be anonymous.
- PDF responses: `Response(content=pdf_bytes, media_type="application/pdf",
  headers={"Content-Disposition": f'attachment; filename="{invoice_number}.pdf"'})`.
- Path/param parsing: validate `month` against `^\d{4}-\d{2}$` → 422/400 with a clear message.
- 404 when a requested invoice id does not exist.

### 8. Frontend

- `src/types/api.ts`: add `InvoiceLineRead`, `InvoiceRead`, `InvoiceListResponse`.
- `src/api/client.ts`:
  - `listInvoices(month)`, `generateInvoices(month)` (admin),
  - `downloadInvoicePdf(month, tenantId?)` → `apiClient.get(..., { responseType: 'blob' })`,
  - `downloadEstateSummaryPdf(month)` → blob,
  - shared `saveBlob(blob, filename)` helper using `URL.createObjectURL` + anchor click +
    `revokeObjectURL` (no download code exists anywhere today).
  - Derive filename from `Content-Disposition` when present.
- `src/pages/BillingPage.tsx` (admin):
  - header action area (lines 56-69, next to the month `<select>`): **"Estate Summary PDF"**
    button with a `loading` state,
  - the "Tenant Billing Breakdown" table (line 155-194): new **PDF** action column, one
    per-row download button (`Download` icon from lucide-react, consistent with existing icons).
- `src/pages/TenantPortalPage.tsx` (tenant): **"Download Invoice (PDF)"** button in the header
  row of the "Tenant Billing Details Card" (lines 293-301), next to the rate badge; downloads
  only the tenant's own invoice (`tenant_id` omitted → server forces own).
- Errors surfaced via the page's existing `error` state / small inline message; buttons disabled
  while a download is in flight.
- No route/guard changes needed: `/billing` is already `RequireAdmin`, `/portal` is
  `RequireTenant`.

### 9. Optional CLI — `scripts/generate_invoice_pdf.py`

Matches the `scripts/` convention (inserts project root on `sys.path` like `seed_demo.py`):
`python scripts/generate_invoice_pdf.py --month 2026-08 [--tenant-id 3 | --estate] [--out dir]`.
Useful for admins/CI and for verifying the renderer without a browser.

### 10. Tests — new `tests/test_invoice_routes.py`

Follow `tests/test_auth.py` role-matrix + `tests/test_estate_routes.py` helper style
(`_admin_token`, `_auth`, local tenant/user factory via `db_session`):

- **Auth**: anonymous → 401 on all invoice endpoints.
- **Role**: tenant hits `POST /generate` and `GET …/estate/summary.pdf` → 403
  ("Role 'TENANT' is not permitted…").
- **Isolation**: tenant requesting `pdf?month=…&tenant_id=<other>` → 403 with
  `"Access denied"`; admin requesting any tenant → 200.
- **PDF correctness**: response `content-type == application/pdf`, body starts with `%PDF`,
  `Content-Disposition` contains a `.pdf` filename.
- **Persistence/idempotency**: `ensure_invoices_for_month` run twice → same row count, same
  `invoice_number`; line items rebuilt not appended.
- **Renderer unit test**: `render_invoice_pdf` / `render_estate_summary_pdf` return `bytes`
  beginning with `%PDF` and contain no `None`/`nan` artifacts.
- Existing billing tests must remain green after the service refactor.

### 11. Verification

1. `pytest` — full suite (old + new).
2. `npm run lint` (`tsc --noEmit`) — frontend types.
3. Manual smoke: `uvicorn app.main:app --reload`, login `ADMIN/4005`, then
   `curl -H "Authorization: Bearer …" -o inv.pdf "http://localhost:8000/api/billing/invoices/pdf?month=2026-08&tenant_id=1"`
   and confirm `%PDF-` magic bytes; repeat as `T258/101` without `tenant_id`.
4. `npm run dev` → `/billing` (estate + per-row PDF buttons) and `/portal` (own-invoice button).

## Files touched

| File | Change |
|---|---|
| `requirements.txt`, `requirements-dev.txt` | add `reportlab` |
| `app/models/invoice.py` | **new** — `Invoice`, `InvoiceLineItem` |
| `app/models/base.py` | register new models |
| `app/services/billing.py` | **new** — summary logic moved out of the router |
| `app/api/routes_billing.py` | thin wrapper over `app/services/billing.py` |
| `app/services/invoicing.py` | **new** — idempotent invoice builder |
| `app/services/pdf_invoice.py` | **new** — reportlab renderers |
| `app/schemas/invoice.py` | **new** — invoice Pydantic schemas |
| `app/api/routes_invoices.py` | **new** — 4 endpoints |
| `app/main.py` | register invoices router |
| `src/types/api.ts` | invoice types |
| `src/api/client.ts` | invoice calls + blob download helper |
| `src/pages/BillingPage.tsx` | estate PDF button + per-row PDF column |
| `src/pages/TenantPortalPage.tsx` | own-invoice download button |
| `scripts/generate_invoice_pdf.py` | **new** — CLI |
| `tests/test_invoice_routes.py` | **new** — role/isolation/PDF tests |

## Out of scope

- Payment status workflows (only a simple `status` column, default `ISSUED`).
- Emailing invoices.
- Logo/branding assets (none exist; PDF uses a drawn header band).
- Replacing the demo billing numbers with real metered data (source of truth stays the existing
  `/billing/summary` data until the real billing engine lands).
