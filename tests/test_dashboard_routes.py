"""Tests for domain API routers (Load Profiles, Solar, Forecasting, Allocation, Battery, Billing, Analytics, Dashboard).

Every route exercised here is behind authentication (see tests/test_api_auth_enforcement.py
for the 401/403 matrix), so these tests pass an ADMIN token.
"""

import pytest


def test_load_profiles_routes(client, admin_auth):
    res_list = client.get("/api/load-profiles", headers=admin_auth)
    assert res_list.status_code == 200
    data_list = res_list.json()
    assert "profiles" in data_list
    assert "total_count" in data_list
    assert "selected_count" in data_list

    res_sel = client.get("/api/load-profiles/selected", headers=admin_auth)
    assert res_sel.status_code == 200
    sel_profiles = res_sel.json()
    assert isinstance(sel_profiles, list)


def test_solar_routes(client, admin_auth):
    res_cfg = client.get("/api/solar/pv-config", headers=admin_auth)
    assert res_cfg.status_code == 200
    cfg = res_cfg.json()
    assert "capacity_kw" in cfg

    res_gen = client.get("/api/solar/generation", headers=admin_auth)
    assert res_gen.status_code == 200
    gen = res_gen.json()
    assert "records" in gen
    assert len(gen["records"]) > 0


def test_forecasting_routes(client, admin_auth):
    res_solar = client.get("/api/forecasting/solar", headers=admin_auth)
    assert res_solar.status_code == 200
    solar_fc = res_solar.json()
    assert solar_fc["is_demo"] is True
    assert len(solar_fc["forecast_data"]) == 24

    res_tenant = client.get("/api/forecasting/tenants/1", headers=admin_auth)
    assert res_tenant.status_code == 200
    tenant_fc = res_tenant.json()
    assert tenant_fc["is_demo"] is False
    assert len(tenant_fc["forecast_data"]) == 24


def test_allocation_routes(client, admin_auth, make_tenant_token):
    # Allocation rows are built from the estate's real Tenant rows, so the
    # endpoint has nothing to report until tenants exist.
    for tenant_id in (1, 2):
        make_tenant_token(tenant_id)

    res_alloc = client.get("/api/allocation/current", headers=admin_auth)
    assert res_alloc.status_code == 200
    alloc = res_alloc.json()
    assert alloc["is_demo"] is True
    assert len(alloc["allocations"]) > 0


def test_battery_routes(client, admin_auth):
    res_cfg = client.get("/api/battery/config", headers=admin_auth)
    assert res_cfg.status_code == 200
    cfg = res_cfg.json()
    assert "capacity_kwh" in cfg

    res_status = client.get("/api/battery/status", headers=admin_auth)
    assert res_status.status_code == 200
    stat = res_status.json()
    assert stat["is_demo"] is True
    assert "current_soc_pct" in stat


def test_billing_routes(client, admin_auth):
    res_tariffs = client.get("/api/billing/tariffs", headers=admin_auth)
    assert res_tariffs.status_code == 200
    tariffs = res_tariffs.json()
    assert "periods" in tariffs
    assert len(tariffs["periods"]) > 0

    res_summary = client.get("/api/billing/summary", headers=admin_auth)
    assert res_summary.status_code == 200
    summary = res_summary.json()
    assert summary["is_demo"] is True
    assert len(summary["tenants"]) > 0


def test_analytics_routes(client, admin_auth):
    res = client.get("/api/analytics/overview", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert data["is_demo"] is False
    assert "total_public_series" in data
    assert "total_observations" in data
    assert "selected_profiles_count" in data


def test_dashboard_routes(client, admin_auth):
    res = client.get("/api/dashboard/overview", headers=admin_auth)
    assert res.status_code == 200
    data = res.json()
    assert data["is_demo"] is True
    assert "dataset_metrics" in data
    assert "solar_metrics" in data
    assert "battery_metrics" in data
    assert "allocation_metrics" in data
    assert "billing_metrics" in data
    assert "selected_profiles_summary" in data
