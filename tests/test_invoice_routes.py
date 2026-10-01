"""Tests for invoice listing, generation, PDF download and role isolation."""

from app.models.enums import TenantProfileType


MONTH = "2026-08"


def _register_admin(client, email="admin@example.com", password="AdminPass123!"):
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "role": "ADMIN"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _register_tenant_user(client, db_session, email, password, tenant_name="Food Processing"):
    from app.models.estate import Estate
    from app.models.tenant import Tenant

    estate = db_session.query(Estate).first()
    if estate is None:
        estate = Estate(name="Coimbatore Demo Estate", latitude=11.0168, longitude=76.9558)
        db_session.add(estate)
        db_session.commit()
        db_session.refresh(estate)

    tenant = Tenant(
        estate_id=estate.id,
        name=tenant_name,
        profile_type=TenantProfileType.FOOD_PROCESSING,
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "role": "TENANT", "tenant_id": tenant.id},
    )
    assert resp.status_code == 201, resp.text
    return tenant


def _login(client, email, password):
    resp = client.post(
        "/api/auth/login",
        data={"username": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _admin_session(client):
    _register_admin(client)
    token = _login(client, "admin@example.com", "AdminPass123!")
    return _auth(token)


# ── Authentication ─────────────────────────────────────────────────────────


def test_invoices_require_authentication(client):
    assert client.get(f"/api/billing/invoices?month={MONTH}").status_code == 401
    assert client.get(f"/api/billing/invoices/pdf?month={MONTH}&tenant_id=1").status_code == 401
    assert client.get(f"/api/billing/invoices/estate/summary.pdf?month={MONTH}").status_code == 401
    assert client.post("/api/billing/invoices/generate", json={"month": MONTH}).status_code == 401


# ── Generation (admin) ─────────────────────────────────────────────────────


def test_admin_can_generate_invoices_for_all_tenants(client):
    headers = _admin_session(client)
    resp = client.post(
        "/api/billing/invoices/generate",
        json={"month": MONTH},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["billing_period"] == MONTH
    assert body["count"] == 6
    numbers = [i["invoice_number"] for i in body["invoices"]]
    assert numbers == [f"SS-{MONTH}-T{n:04d}" for n in range(1, 7)]
    first = body["invoices"][0]
    assert first["tenant_id"] == 1
    assert first["total_bill_inr"] > 0
    assert len(first["line_items"]) >= 4
    assert any(li["category"] == "SOLAR" for li in first["line_items"])
    assert any(li["category"] == "GRID" for li in first["line_items"])
    assert any(li["category"] == "TOTAL" for li in first["line_items"])


def test_generation_is_idempotent(client, db_session):
    from app.models.invoice import Invoice, InvoiceLineItem

    headers = _admin_session(client)
    first = client.post("/api/billing/invoices/generate", json={"month": MONTH}, headers=headers)
    second = client.post("/api/billing/invoices/generate", json={"month": MONTH}, headers=headers)
    assert first.status_code == 200 and second.status_code == 200
    assert second.json()["count"] == first.json()["count"]

    invoice_count = db_session.query(Invoice).count()
    line_count = db_session.query(InvoiceLineItem).count()
    assert invoice_count == 6
    assert line_count == 6 * len(first.json()["invoices"][0]["line_items"])


def test_generate_rejects_invalid_month(client):
    headers = _admin_session(client)
    resp = client.post("/api/billing/invoices/generate", json={"month": "2026-13"}, headers=headers)
    assert resp.status_code == 422


def test_tenant_cannot_generate(client, db_session):
    tenant = _register_tenant_user(client, db_session, "t@example.com", "TenantPass123!")
    token = _login(client, "t@example.com", "TenantPass123!")
    resp = client.post(
        "/api/billing/invoices/generate",
        json={"month": MONTH},
        headers=_auth(token),
    )
    assert resp.status_code == 403
    assert "TENANT" in resp.json()["detail"]
    assert tenant is not None


# ── Listing ────────────────────────────────────────────────────────────────


def test_admin_lists_all_invoices(client):
    headers = _admin_session(client)
    client.post("/api/billing/invoices/generate", json={"month": MONTH}, headers=headers)
    resp = client.get(f"/api/billing/invoices?month={MONTH}", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["count"] == 6


def test_tenant_lists_only_own_invoice(client, db_session):
    from app.models.invoice import Invoice

    _register_admin(client)
    admin_headers = _auth(_login(client, "admin@example.com", "AdminPass123!"))

    tenant = _register_tenant_user(client, db_session, "only-me@example.com", "TenantPass123!")
    # Tenant row created in the test DB gets id 1 -> matches demo tenant 1.
    assert tenant.id in (1, 2, 3, 4, 5, 6)

    client.post("/api/billing/invoices/generate", json={"month": MONTH}, headers=admin_headers)
    assert db_session.query(Invoice).count() == 6

    token = _login(client, "only-me@example.com", "TenantPass123!")
    resp = client.get(f"/api/billing/invoices?month={MONTH}", headers=_auth(token))
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["invoices"][0]["tenant_id"] == tenant.id


# ── PDF download ───────────────────────────────────────────────────────────


def test_admin_downloads_individual_invoice_pdf(client):
    headers = _admin_session(client)
    resp = client.get(
        f"/api/billing/invoices/pdf?month={MONTH}&tenant_id=1",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"
    assert "SS-" in resp.headers["content-disposition"]
    assert resp.headers["content-disposition"].endswith('.pdf"')


def test_admin_pdf_requires_tenant_id(client):
    headers = _admin_session(client)
    resp = client.get(f"/api/billing/invoices/pdf?month={MONTH}", headers=headers)
    assert resp.status_code == 400
    assert "tenant_id" in resp.json()["detail"]


def test_admin_pdf_unknown_tenant_returns_404(client):
    headers = _admin_session(client)
    resp = client.get(
        f"/api/billing/invoices/pdf?month={MONTH}&tenant_id=999",
        headers=headers,
    )
    assert resp.status_code == 404


def test_tenant_downloads_own_invoice_pdf(client, db_session):
    tenant = _register_tenant_user(client, db_session, "me@example.com", "TenantPass123!")
    token = _login(client, "me@example.com", "TenantPass123!")

    # No tenant_id supplied -> server forces own tenant, generates on demand.
    resp = client.get(f"/api/billing/invoices/pdf?month={MONTH}", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"
    assert f"T{tenant.id:04d}" in resp.headers["content-disposition"]


def test_tenant_cannot_download_other_tenants_pdf(client, db_session):
    _register_tenant_user(client, db_session, "tenant-a@example.com", "TenantPass123!")
    tenant_b = _register_tenant_user(client, db_session, "tenant-b@example.com", "TenantPass123!")
    token = _login(client, "tenant-a@example.com", "TenantPass123!")

    # tenant-a is tenant id 1; ask for tenant-b's invoice.
    resp = client.get(
        f"/api/billing/invoices/pdf?month={MONTH}&tenant_id={tenant_b.id}",
        headers=_auth(token),
    )
    assert resp.status_code == 403
    assert "Access denied" in resp.json()["detail"]


def test_estate_summary_pdf_admin_only(client, db_session):
    # Admin: 200 + valid PDF
    headers = _admin_session(client)
    resp = client.get(
        f"/api/billing/invoices/estate/summary.pdf?month={MONTH}",
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"
    assert f"Summary-{MONTH}.pdf" in resp.headers["content-disposition"]

    # Tenant: 403
    _register_tenant_user(client, db_session, "locked-out@example.com", "TenantPass123!")
    token = _login(client, "locked-out@example.com", "TenantPass123!")
    resp = client.get(
        f"/api/billing/invoices/estate/summary.pdf?month={MONTH}",
        headers=_auth(token),
    )
    assert resp.status_code == 403


def test_invalid_month_rejected_on_list(client):
    headers = _admin_session(client)
    resp = client.get("/api/billing/invoices?month=2026-13", headers=headers)
    assert resp.status_code == 422


# ── Renderer unit tests ────────────────────────────────────────────────────


def test_render_invoice_pdf_returns_valid_bytes(db_session):
    from app.services.invoicing import ensure_invoices_for_month
    from app.services.pdf_invoice import render_invoice_pdf

    invoices = ensure_invoices_for_month(db_session, MONTH, None)
    assert len(invoices) == 6
    pdf = render_invoice_pdf(
        invoices[0],
        tenant_name="Textile Manufacturing Unit",
        estate_name="Coimbatore Demo Estate",
        tariff=None,
    )
    assert isinstance(pdf, bytes)
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 1000


def test_render_estate_summary_pdf_returns_valid_bytes(db_session):
    from app.services.invoicing import ensure_invoices_for_month
    from app.services.pdf_invoice import render_estate_summary_pdf

    invoices = ensure_invoices_for_month(db_session, MONTH, None)
    pdf = render_estate_summary_pdf(
        MONTH,
        invoices,
        estate_name="Coimbatore Demo Estate",
        tenant_names={i: f"Tenant {i}" for i in range(1, 7)},
    )
    assert isinstance(pdf, bytes)
    assert pdf[:5] == b"%PDF-"


def test_invoice_line_items_rebuilt_not_duplicated(db_session):
    from app.models.invoice import Invoice, InvoiceLineItem
    from app.services.invoicing import ensure_invoices_for_month

    ensure_invoices_for_month(db_session, MONTH, 1)
    first_lines = (
        db_session.query(InvoiceLineItem)
        .join(Invoice)
        .filter(Invoice.tenant_id == 1, Invoice.billing_period == MONTH)
        .count()
    )
    ensure_invoices_for_month(db_session, MONTH, 1)
    second_lines = (
        db_session.query(InvoiceLineItem)
        .join(Invoice)
        .filter(Invoice.tenant_id == 1, Invoice.billing_period == MONTH)
        .count()
    )
    assert first_lines == second_lines
    assert db_session.query(Invoice).filter(Invoice.billing_period == MONTH).count() == 1