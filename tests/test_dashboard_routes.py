"""Tests for domain API routers (Load Profiles, Solar, Forecasting, Allocation, Battery, Billing, Analytics, Dashboard)."""

import pytest


def test_load_profiles_routes(client):
    res_list = client.get("/api/load-profiles")
    assert res_list.status_code == 200
    data_list = res_list.json()
    assert "profiles" in data_list
    assert "total_count" in data_list
    assert "selected_count" in data_list

    res_sel = client.get("/api/load-profiles/selected")
    assert res_sel.status_code == 200
    sel_profiles = res_sel.json()
    assert isinstance(sel_profiles, list)


def test_solar_routes(client):
    res_cfg = client.get("/api/solar/pv-config")
    assert res_cfg.status_code == 200
    cfg = res_cfg.json()
    assert "capacity_kw" in cfg

    res_gen = client.get("/api/solar/generation")
    assert res_gen.status_code == 200
    gen = res_gen.json()
    assert "records" in gen
    assert len(gen["records"]) > 0


def test_forecasting_routes(client):
    res_solar = client.get("/api/forecasting/solar")
    assert res_solar.status_code == 200
    solar_fc = res_solar.json()
    assert solar_fc["is_demo"] is True
    assert len(solar_fc["forecast_data"]) == 24

    res_tenant = client.get("/api/forecasting/tenants/1")
    assert res_tenant.status_code == 200
    tenant_fc = res_tenant.json()
    assert tenant_fc["is_demo"] is False
    assert len(tenant_fc["forecast_data"]) == 24


def test_allocation_routes(client):
    res_alloc = client.get("/api/allocation/current")
    assert res_alloc.status_code == 200
    alloc = res_alloc.json()
    assert alloc["is_demo"] is True
    assert len(alloc["allocations"]) > 0


def test_battery_routes(client):
    res_cfg = client.get("/api/battery/config")
    assert res_cfg.status_code == 200
    cfg = res_cfg.json()
    assert "capacity_kwh" in cfg

    res_status = client.get("/api/battery/status")
    assert res_status.status_code == 200
    stat = res_status.json()
    assert stat["is_demo"] is True
    assert "current_soc_pct" in stat


def test_billing_routes(client):
    res_tariffs = client.get("/api/billing/tariffs")
    assert res_tariffs.status_code == 200
    tariffs = res_tariffs.json()
    assert "periods" in tariffs
    assert len(tariffs["periods"]) > 0

    res_summary = client.get("/api/billing/summary")
    assert res_summary.status_code == 200
    summary = res_summary.json()
    assert summary["is_demo"] is True
    assert len(summary["tenants"]) > 0


def test_analytics_routes(client):
    res = client.get("/api/analytics/overview")
    assert res.status_code == 200
    data = res.json()
    assert data["is_demo"] is False
    assert "total_public_series" in data
    assert "total_observations" in data
    assert "selected_profiles_count" in data


def test_dashboard_routes(client):
    res = client.get("/api/dashboard/overview")
    assert res.status_code == 200
    data = res.json()
    assert data["is_demo"] is True
    assert "dataset_metrics" in data
    assert "solar_metrics" in data
    assert "battery_metrics" in data
    assert "allocation_metrics" in data
    assert "billing_metrics" in data
    assert "selected_profiles_summary" in data
