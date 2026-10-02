"""
Authentication / authorization enforcement across the whole API surface.

Before this suite existed, only `/api/invoices/*` and `/api/demo/*` were behind a
role check: dashboards, billing summaries, forecasts, allocation and load
profiles answered 200 to an anonymous caller, so a plain `curl` with no token
read the entire estate's operational and financial data. These tests pin the
contract down so a future route cannot silently re-open it:

* no endpoint except `/api/health` hands out data without a valid token;
* estate-wide / configuration endpoints are ADMIN-only (403 for TENANT);
* tenant-scoped endpoints return only the calling tenant's own data.
"""

import pytest

from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.enums import UserRole
from app.models.user import User

# Endpoints reachable without any credentials. FastAPI's auto-generated docs are
# included deliberately: they expose no data, and they are useful during a demo.
PUBLIC_PATHS = ["/api/health", "/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"]

# GET endpoints that need no query/path arguments — these must answer exactly 401.
UNAUTH_NO_PARAM_PATHS = [
    "/api/estates",
    "/api/estates/active",
    "/api/estates/presets",
    "/api/load-profiles",
    "/api/load-profiles/selected",
    "/api/solar/pv-config",
    "/api/solar/generation",
    "/api/battery/config",
    "/api/battery/status",
    "/api/allocation/current",
    "/api/billing/tariffs",
    "/api/billing/summary",
    "/api/analytics/overview",
    "/api/dashboard/overview",
    "/api/forecasting/solar",
]

# (path) — TENANT is authenticated but not permitted.
ADMIN_ONLY_PATHS = [
    "/api/dashboard/overview",
    "/api/analytics/overview",
    "/api/load-profiles",
    "/api/load-profiles/T258",
    "/api/solar/pv-config",
    "/api/battery/config",
    "/api/billing/tariffs",
    "/api/forecasting/solar",
]

# Endpoints any authenticated role may read (shared-estate read models).
SHARED_READ_PATHS = [
    "/api/estates",
    "/api/estates/active",
    "/api/estates/1",
    "/api/estates/presets",
    "/api/load-profiles/selected",
    "/api/solar/generation",
    "/api/battery/status",
    "/api/allocation/current",
    "/api/billing/summary",
    "/api/forecasting/tenants/1",
]


# The sweep below is only meaningful if route enumeration actually works. Newer
# Starlette versions wrap `include_router` results in an `_IncludedRouter` object
# that has neither `.path` nor `.methods`, so a naive `[r.path for r in app.routes]`
# silently enumerates nothing and the sweep passes without testing anything.
_MIN_ENUMERATED_API_GET_PATHS = 25


def _all_get_paths():
    """Every GET path on the app.

    Read from the generated OpenAPI schema rather than `app.routes`: on newer
    Starlette versions `app.routes` holds `_IncludedRouter` wrappers whose
    children carry un-prefixed paths, so walking it yields wrong (or zero)
    paths. The schema is what `/openapi.json` serves, so it is by construction
    the surface a caller can actually reach.
    """
    schema_get_paths = [
        path for path, operations in app.openapi()["paths"].items() if "get" in operations
    ]
    paths = sorted(set(schema_get_paths) | set(PUBLIC_PATHS))

    api_paths = [p for p in paths if p.startswith("/api/")]
    assert len(api_paths) >= _MIN_ENUMERATED_API_GET_PATHS, (
        f"route enumeration found only {len(api_paths)} /api GET paths "
        f"({len(paths)} total) — this sweep would test nothing"
    )
    return paths


def _concrete(path):
    """Replace `{param}` placeholders so the sweep probes real routes, not 422s."""
    while "{" in path:
        start = path.index("{")
        end = path.index("}", start)
        path = path[:start] + "1" + path[end + 1:]
    return path


def test_health_is_public(client):
    assert client.get("/api/health").status_code == 200


@pytest.mark.parametrize("path", UNAUTH_NO_PARAM_PATHS)
def test_endpoints_require_authentication(client, path):
    assert client.get(path).status_code == 401, f"{path} answered an unauthenticated caller"


@pytest.mark.parametrize("path", _all_get_paths())
def test_no_get_endpoint_ever_returns_data_to_anonymous_callers(client, path):
    """Every API GET must refuse anonymous callers with 401/403, not 200/422/404."""
    if path in PUBLIC_PATHS or path == "/":
        return
    probe = client.get(_concrete(path))
    assert probe.status_code in (401, 403), (
        f"{path} did not refuse an anonymous caller: {probe.status_code} {probe.text[:120]}"
    )


@pytest.mark.parametrize("path", ADMIN_ONLY_PATHS)
def test_admin_only_endpoints_reject_tenants(client, tenant_auth, path):
    assert client.get(path, headers=tenant_auth).status_code == 403


@pytest.mark.parametrize("path", SHARED_READ_PATHS)
def test_shared_read_endpoints_allow_tenants(client, tenant_auth, path):
    res = client.get(path, headers=tenant_auth)
    assert res.status_code == 200, f"{path} -> {res.status_code}: {res.text}"


@pytest.mark.parametrize("path", UNAUTH_NO_PARAM_PATHS)
def test_garbage_token_is_rejected(client, path):
    assert client.get(path, headers={"Authorization": "Bearer not-a-real-jwt"}).status_code == 401


def test_admin_can_read_the_whole_allocation_split(client, admin_auth, make_tenant_token):
    for tenant_id in (1, 2, 3):
        make_tenant_token(tenant_id)
    res = client.get("/api/allocation/current", headers=admin_auth)
    assert res.status_code == 200
    assert len(res.json()["allocations"]) > 1


def test_tenant_only_sees_its_own_allocation_row(client, make_tenant_token):
    headers = {"Authorization": f"Bearer {make_tenant_token(2)}"}

    res = client.get("/api/allocation/current", headers=headers)
    assert res.status_code == 200
    assert [row["tenant_id"] for row in res.json()["allocations"]] == [2]


def test_tenant_cannot_read_another_tenants_forecast(client, make_tenant_token):
    headers = {"Authorization": f"Bearer {make_tenant_token(1)}"}
    assert client.get("/api/forecasting/tenants/2", headers=headers).status_code == 403
    assert client.get("/api/forecasting/tenants/1", headers=headers).status_code == 200


def test_tenant_cannot_read_another_tenants_bill(client, make_tenant_token):
    headers = {"Authorization": f"Bearer {make_tenant_token(1)}"}
    assert client.get("/api/billing/summary?tenant_id=2", headers=headers).status_code == 403


def test_tenant_billing_summary_is_pinned_to_own_tenant(client, make_tenant_token):
    headers = {"Authorization": f"Bearer {make_tenant_token(1)}"}

    res = client.get("/api/billing/summary", headers=headers)
    assert res.status_code == 200
    body = res.json()
    # Even without an explicit filter, a tenant must never receive the
    # estate-wide roll-up of every tenant's charges.
    assert all(entry["tenant_id"] == 1 for entry in body["tenants"])


def test_tenant_without_tenant_link_is_denied(client, db_session):
    """A TENANT account with no tenant_id must 403, not fall back to estate-wide data."""
    orphan = User(
        email="orphan-tenant@example.com",
        hashed_password=hash_password("OrphanPass123!"),
        role=UserRole.TENANT,
        tenant_id=None,
    )
    db_session.add(orphan)
    db_session.commit()
    db_session.refresh(orphan)

    headers = {
        "Authorization": f"Bearer {create_access_token(subject=orphan.id, role=orphan.role.value)}"
    }

    assert client.get("/api/billing/summary", headers=headers).status_code == 403
    assert client.get("/api/forecasting/tenants/1", headers=headers).status_code == 403

    res = client.get("/api/allocation/current", headers=headers)
    assert res.status_code == 200
    assert res.json()["allocations"] == []


# --- tenant ids that fall outside the hardcoded demo ranges --------------------
#
# The demo seed numbers (billing rows, allocation profiles) are keyed by the ids
# the seed happens to produce. A tenant whose id lands outside those ranges — a
# second estate, a manually created tenant, a database seeded twice — used to be
# handled by falling back to estate-wide data or by matching nothing at all. Both
# are wrong: the caller must still get their own row and nobody else's.

_OUT_OF_RANGE_TENANT_ID = 7


def test_tenant_allocation_row_survives_an_id_outside_the_demo_range(client, make_tenant_token):
    for tenant_id in range(1, _OUT_OF_RANGE_TENANT_ID):
        make_tenant_token(tenant_id)
    headers = {"Authorization": f"Bearer {make_tenant_token(_OUT_OF_RANGE_TENANT_ID)}"}

    res = client.get("/api/allocation/current", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert [row["tenant_id"] for row in body["allocations"]] == [_OUT_OF_RANGE_TENANT_ID]
    assert body["allocations"][0]["tenant_name"].startswith("Test Tenant")


def test_tenant_billing_never_falls_back_to_estate_totals_for_an_unknown_id(client, make_tenant_token):
    """An unmatched tenant id must yield an empty summary, never the whole estate."""
    headers = {"Authorization": f"Bearer {make_tenant_token(_OUT_OF_RANGE_TENANT_ID)}"}

    res = client.get("/api/billing/summary", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["tenants"] == []
    assert body["total_estate_consumption_kwh"] == 0.0
    assert body["total_savings_inr"] == 0.0


def test_tenant_billing_matches_its_own_row_by_name(client, make_tenant_token):
    """A tenant whose id is unknown but whose name matches a demo row gets that row."""
    headers = {"Authorization": f"Bearer {make_tenant_token(3, tenant_name='Electronics Assembly')}"}

    res = client.get("/api/billing/summary", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert [t["tenant_id"] for t in body["tenants"]] == [3]
    assert body["tenants"][0]["tenant_name"] == "Electronics Assembly"
    # Totals must describe the single tenant, not the estate.
    assert body["total_estate_consumption_kwh"] == body["tenants"][0]["total_consumption_kwh"]


def test_allocation_rows_are_keyed_to_real_tenant_rows(client, make_tenant_token):
    """Allocation ids/names come from the DB, not from a hardcoded 1..N list."""
    make_tenant_token(1, tenant_name="Alpha Works")
    headers = {"Authorization": f"Bearer {make_tenant_token(9, tenant_name='Beta Works')}"}

    res = client.get("/api/allocation/current", headers=headers)
    assert res.status_code == 200
    row = res.json()["allocations"][0]
    assert row["tenant_id"] == 9
    assert row["tenant_name"] == "Beta Works"


def test_tenant_invoice_filter_is_rejected_not_ignored(client, make_tenant_token):
    """Asking for another tenant's invoices is a 403, not a quietly ignored filter."""
    make_tenant_token(1)
    headers = {"Authorization": f"Bearer {make_tenant_token(2)}"}

    res = client.get("/api/billing/invoices?tenant_id=1", headers=headers)
    assert res.status_code == 403

    res = client.get("/api/billing/invoices?tenant_id=2", headers=headers)
    assert res.status_code == 200
    assert {i["tenant_id"] for i in res.json()["invoices"]} <= {2}


def test_admin_can_filter_invoices_by_tenant(client, admin_auth, make_tenant_token):
    make_tenant_token(1)
    make_tenant_token(2)

    res = client.get("/api/billing/invoices?tenant_id=2", headers=admin_auth)
    assert res.status_code == 200
    assert {i["tenant_id"] for i in res.json()["invoices"]} <= {2}
