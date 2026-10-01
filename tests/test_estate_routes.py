"""
Tests for Estate location management and coordinate-driven NASA POWER sync.

The NASA POWER transport is monkeypatched in every sync test so the suite stays
offline and deterministic — the real HTTP client's URL/cache-key construction is
covered separately in tests/test_nasa_power_url_and_cache_key.py.

The most important test here is `test_changing_coordinates_purges_stale_rows`:
`WeatherObservation`/`SolarGenerationEstimate` are keyed by (estate_id, timestamp)
only, so moving an estate must discard rows recorded at the old coordinates,
otherwise one estate's time series silently blends two locations.
"""

import pytest

from datetime import date, datetime, timedelta, timezone

from app.core.security import hash_password
from app.models.config import PVConfig
from app.models.enums import UserRole
from app.models.estate import Estate
from app.models.weather import SolarGenerationEstimate, WeatherObservation
from app.schemas.estate import PRESET_ESTATES

FAKE_OBSERVATION_COUNT = 6


# ─── helpers ───────────────────────────────────────────────


def _admin_token(client, email="estate-admin@example.com", password="EstatePass123!"):
    resp = client.post(
        "/api/auth/register",
        json={"email": email, "password": password, "role": "ADMIN"},
    )
    assert resp.status_code == 201, resp.text
    login = client.post("/api/auth/login", data={"username": email, "password": password})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _make_estate(db_session, name="Coimbatore Demo Estate", lat=11.0168, lon=76.9558):
    estate = Estate(name=name, latitude=lat, longitude=lon, timezone="Asia/Kolkata")
    db_session.add(estate)
    db_session.commit()
    db_session.refresh(estate)
    return estate


def _seed_observations(db_session, estate, lat, lon, count=FAKE_OBSERVATION_COUNT):
    """Persist `count` hourly observations tagged with the given coordinates."""
    from datetime import datetime, timedelta, timezone

    base = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    for hour in range(count):
        db_session.add(
            WeatherObservation(
                estate_id=estate.id,
                timestamp=base + timedelta(hours=hour),
                allsky_sfc_sw_dwn=100.0 * (hour + 1),
                t2m=28.0,
                rh2m=55.0,
                ws10m=3.0,
                source_url="https://power.larc.nasa.gov/api/temporal/hourly/point",
                parameters_requested="ALLSKY_SFC_SW_DWN,T2M",
                latitude=lat,
                longitude=lon,
                retrieved_at=base,
            )
        )
    db_session.commit()


def _install_fake_nasa(monkeypatch, ghi=800.0, missing_every=None):
    """
    Replace `ingest_nasa_power_range` inside the estate router with a fake that
    writes observations tagged with the estate's current coordinates. This keeps
    the route's own logic (purging, PV provisioning, response assembly) under
    test without touching the network.

    `ghi=None` simulates a window NASA POWER has not processed yet (all fill
    values -> NULL GHI). `missing_every=N` simulates periodic gaps (nighttime).
    """
    from app.api import routes_estate
    from datetime import datetime, timedelta, timezone

    written = {"observations": 0, "coords": None}

    def _fake(db, estate, start_date, end_date, parameters=None, use_cache=True):
        base = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
        for hour in range(FAKE_OBSERVATION_COUNT):
            is_gap = missing_every is not None and (hour % missing_every == 0)
            db.add(
                WeatherObservation(
                    estate_id=estate.id,
                    timestamp=base + timedelta(hours=hour),
                    allsky_sfc_sw_dwn=None if (ghi is None or is_gap) else ghi,
                    t2m=30.0,
                    rh2m=50.0,
                    ws10m=2.0,
                    source_url="https://power.larc.nasa.gov/api/temporal/hourly/point",
                    parameters_requested="ALLSKY_SFC_SW_DWN,T2M",
                    latitude=estate.latitude,
                    longitude=estate.longitude,
                    retrieved_at=base,
                )
            )
        db.commit()
        written["observations"] = FAKE_OBSERVATION_COUNT
        written["coords"] = (estate.latitude, estate.longitude)
        return {
            "records_written": FAKE_OBSERVATION_COUNT,
            "data_status": "LIVE",
            "cache_hit": False,
        }

    monkeypatch.setattr(routes_estate, "ingest_nasa_power_range", _fake)
    return written


# ─── presets ───────────────────────────────────────────────


def test_presets_are_listed_without_auth(client):
    resp = client.get("/api/estates/presets")
    assert resp.status_code == 200, resp.text
    presets = resp.json()
    assert len(presets) == len(PRESET_ESTATES)
    coimbatore = next(p for p in presets if p["id"] == "coimbatore-msme")
    assert coimbatore["latitude"] == pytest.approx(11.0168)
    assert coimbatore["longitude"] == pytest.approx(76.9558)


def test_all_presets_have_valid_coordinate_ranges(client):
    for preset in client.get("/api/estates/presets").json():
        assert -90.0 <= preset["latitude"] <= 90.0
        assert -180.0 <= preset["longitude"] <= 180.0
        assert preset["timezone"]


# ─── CRUD ──────────────────────────────────────────────────


def test_list_estates_empty(client, db_session):
    assert client.get("/api/estates").json() == []


def test_create_and_read_estate(client, db_session):
    token = _admin_token(client)
    resp = client.post(
        "/api/estates",
        headers=_auth(token),
        json={
            "name": "Chennai Guindy Industrial Estate",
            "latitude": 13.0067,
            "longitude": 80.2206,
            "timezone": "Asia/Kolkata",
        },
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["name"] == "Chennai Guindy Industrial Estate"
    assert created["latitude"] == pytest.approx(13.0067)
    assert created["weather_observation_count"] == 0

    fetched = client.get(f"/api/estates/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["longitude"] == pytest.approx(80.2206)


def test_create_estate_rejects_out_of_range_coordinates(client):
    token = _admin_token(client)
    resp = client.post(
        "/api/estates",
        headers=_auth(token),
        json={"name": "Bad Place", "latitude": 999.0, "longitude": 80.0},
    )
    assert resp.status_code == 422, resp.text


def test_active_estate_returns_lowest_id(client, db_session):
    first = _make_estate(db_session, name="First", lat=11.0, lon=76.0)
    _make_estate(db_session, name="Second", lat=13.0, lon=80.0)

    resp = client.get("/api/estates/active")
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == first.id


def test_active_estate_404s_when_none_configured(client, db_session):
    assert client.get("/api/estates/active").status_code == 404


def test_estate_not_found(client, db_session):
    assert client.get("/api/estates/9999").status_code == 404


# ─── authorization ─────────────────────────────────────────


def _tenant_token(client, db_session):
    """TENANT registration requires a real tenant_id (see app/api/routes_auth.py)."""
    from app.models.enums import TenantProfileType
    from app.models.tenant import Tenant

    estate = db_session.query(Estate).order_by(Estate.id).first()
    tenant = Tenant(
        estate_id=estate.id,
        name="Test Tenant",
        profile_type=TenantProfileType.TEXTILE_MANUFACTURING,
        source_client_series_id="T258",
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    resp = client.post(
        "/api/auth/register",
        json={
            "email": "tenant@example.com",
            "password": "TenantPass123!",
            "role": "TENANT",
            "tenant_id": tenant.id,
        },
    )
    assert resp.status_code == 201, resp.text
    token = client.post(
        "/api/auth/login", data={"username": "tenant@example.com", "password": "TenantPass123!"}
    ).json()["access_token"]
    return token


def test_create_estate_requires_admin(client, db_session):
    estate = _make_estate(db_session)
    token = _tenant_token(client, db_session)

    resp = client.post(
        "/api/estates",
        headers=_auth(token),
        json={"name": "Sneaky", "latitude": 11.0, "longitude": 76.0},
    )
    assert resp.status_code == 403, resp.text


def test_update_estate_requires_authentication(client, db_session):
    estate = _make_estate(db_session)
    resp = client.put(f"/api/estates/{estate.id}", json={"latitude": 12.0})
    assert resp.status_code == 401, resp.text


# ─── coordinate switching ──────────────────────────────────


def test_update_estate_changes_coordinates(client, db_session):
    estate = _make_estate(db_session)
    token = _admin_token(client)

    resp = client.put(
        f"/api/estates/{estate.id}",
        headers=_auth(token),
        json={"latitude": 18.7519, "longitude": 73.8537, "name": "Pune Bhosari MIDC"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["latitude"] == pytest.approx(18.7519)
    assert body["longitude"] == pytest.approx(73.8537)
    assert body["name"] == "Pune Bhosari MIDC"

    db_session.refresh(estate)
    assert estate.latitude == pytest.approx(18.7519)


def test_partial_update_keeps_untouched_fields(client, db_session):
    estate = _make_estate(db_session, name="Original Name")
    token = _admin_token(client)

    resp = client.put(f"/api/estates/{estate.id}", headers=_auth(token), json={"latitude": 20.0})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "Original Name"
    assert body["longitude"] == pytest.approx(76.9558)


def test_changing_coordinates_purges_stale_rows(client, db_session):
    """
    Core data-integrity guarantee: after an estate moves, no row recorded at the
    previous coordinates may survive, and no generation estimate may be left
    orphaned pointing at a deleted observation.
    """
    estate = _make_estate(db_session)
    _seed_observations(db_session, estate, lat=11.0168, lon=76.9558)

    pv = PVConfig(
        estate_id=estate.id,
        capacity_kw=500.0,
        efficiency=0.20,
        performance_ratio=0.80,
        effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        is_active=True,
    )
    db_session.add(pv)
    db_session.commit()
    db_session.refresh(pv)

    from app.services.solar_generation import estimate_for_range

    estimate_for_range(db_session, estate.id, pv)
    assert db_session.query(WeatherObservation).filter_by(estate_id=estate.id).count() == FAKE_OBSERVATION_COUNT
    assert db_session.query(SolarGenerationEstimate).filter_by(estate_id=estate.id).count() == FAKE_OBSERVATION_COUNT

    token = _admin_token(client)
    resp = client.put(
        f"/api/estates/{estate.id}",
        headers=_auth(token),
        json={"latitude": 18.7519, "longitude": 73.8537},
    )
    assert resp.status_code == 200, resp.text

    db_session.expire_all()
    assert db_session.query(WeatherObservation).filter_by(estate_id=estate.id).count() == 0
    assert db_session.query(SolarGenerationEstimate).filter_by(estate_id=estate.id).count() == 0
    # No generation estimate may reference a weather observation that no longer exists.
    orphan = db_session.execute(
        __import__("sqlalchemy").text(
            "SELECT COUNT(*) FROM solar_generation_estimates "
            "WHERE weather_observation_id NOT IN (SELECT id FROM weather_observations)"
        )
    ).scalar()
    assert orphan == 0


def test_renaming_estate_does_not_purge_data(client, db_session):
    """Only a genuine coordinate change may discard ingested data."""
    estate = _make_estate(db_session)
    _seed_observations(db_session, estate, lat=11.0168, lon=76.9558)

    token = _admin_token(client)
    resp = client.put(
        f"/api/estates/{estate.id}",
        headers=_auth(token),
        json={"name": "Renamed Estate Only"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["weather_observation_count"] == FAKE_OBSERVATION_COUNT


def test_negligibly_different_coordinates_do_not_purge(client, db_session):
    """Floating-point noise is not a location change."""
    estate = _make_estate(db_session, lat=11.0168, lon=76.9558)
    _seed_observations(db_session, estate, lat=11.0168, lon=76.9558)

    token = _admin_token(client)
    resp = client.put(
        f"/api/estates/{estate.id}",
        headers=_auth(token),
        json={"latitude": 11.0168 + 1e-9, "longitude": 76.9558},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["weather_observation_count"] == FAKE_OBSERVATION_COUNT


# ─── sync-weather ──────────────────────────────────────────


def test_sync_weather_writes_observations_for_current_coordinates(client, db_session, monkeypatch):
    estate = _make_estate(db_session)
    fake = _install_fake_nasa(monkeypatch, ghi=900.0)
    token = _admin_token(client)

    resp = client.post(
        f"/api/estates/{estate.id}/sync-weather",
        headers=_auth(token),
        json={"start_date": "2026-01-01", "end_date": "2026-01-03"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["estate_id"] == estate.id
    assert body["records_written"] == FAKE_OBSERVATION_COUNT
    assert body["generation_estimates_written"] == FAKE_OBSERVATION_COUNT
    assert body["data_status"] == "LIVE"
    assert fake["coords"] == pytest.approx((11.0168, 76.9558))

    rows = db_session.query(WeatherObservation).filter_by(estate_id=estate.id).all()
    assert len(rows) == FAKE_OBSERVATION_COUNT
    for row in rows:
        assert row.latitude == pytest.approx(11.0168)
        assert row.longitude == pytest.approx(76.9558)


def test_sync_weather_uses_updated_coordinates_after_switch(client, db_session, monkeypatch):
    """The whole point: switch coords, then get data for the NEW coords."""
    estate = _make_estate(db_session)
    fake = _install_fake_nasa(monkeypatch)
    token = _admin_token(client)

    client.put(
        f"/api/estates/{estate.id}",
        headers=_auth(token),
        json={"latitude": 13.0067, "longitude": 80.2206},
    )

    resp = client.post(f"/api/estates/{estate.id}/sync-weather", headers=_auth(token), json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["latitude"] == pytest.approx(13.0067)
    assert body["longitude"] == pytest.approx(80.2206)
    assert fake["coords"] == pytest.approx((13.0067, 80.2206))

    rows = db_session.query(WeatherObservation).filter_by(estate_id=estate.id).all()
    assert rows
    assert all(r.longitude == pytest.approx(80.2206) for r in rows)


def test_sync_weather_auto_provisions_pv_config(client, db_session, monkeypatch):
    estate = _make_estate(db_session)
    _install_fake_nasa(monkeypatch)
    token = _admin_token(client)

    assert db_session.query(PVConfig).filter_by(estate_id=estate.id).count() == 0
    resp = client.post(f"/api/estates/{estate.id}/sync-weather", headers=_auth(token), json={})
    assert resp.status_code == 200, resp.text

    pv = db_session.query(PVConfig).filter_by(estate_id=estate.id).one()
    assert pv.capacity_kw == pytest.approx(500.0)
    assert pv.performance_ratio == pytest.approx(0.80)
    assert resp.json()["pv_config_id"] == pv.id


def test_sync_weather_generation_reflects_new_irradiance(client, db_session, monkeypatch):
    """Different coordinates → different GHI → different generation estimate."""
    estate = _make_estate(db_session)
    _install_fake_nasa(monkeypatch, ghi=1000.0)
    token = _admin_token(client)

    client.post(f"/api/estates/{estate.id}/sync-weather", headers=_auth(token), json={})
    sunny = db_session.query(SolarGenerationEstimate).filter_by(estate_id=estate.id).first()
    # GHI 1000 W/m2 == STC reference → 1.0 kWh/m2 * 500 kW * 0.80 PR
    assert sunny.estimated_kwh == pytest.approx(400.0, rel=1e-6)


def test_sync_weather_rejects_inverted_date_range(client, db_session, monkeypatch):
    estate = _make_estate(db_session)
    _install_fake_nasa(monkeypatch)
    token = _admin_token(client)

    resp = client.post(
        f"/api/estates/{estate.id}/sync-weather",
        headers=_auth(token),
        json={"start_date": "2026-01-10", "end_date": "2026-01-01"},
    )
    assert resp.status_code == 422, resp.text


def test_sync_weather_rejects_oversized_range(client, db_session, monkeypatch):
    estate = _make_estate(db_session)
    _install_fake_nasa(monkeypatch)
    token = _admin_token(client)

    resp = client.post(
        f"/api/estates/{estate.id}/sync-weather",
        headers=_auth(token),
        json={"start_date": "2020-01-01", "end_date": "2026-01-01"},
    )
    assert resp.status_code == 422, resp.text


def test_sync_weather_requires_admin(client, db_session, monkeypatch):
    estate = _make_estate(db_session)
    _install_fake_nasa(monkeypatch)
    token = _tenant_token(client, db_session)

    resp = client.post(f"/api/estates/{estate.id}/sync-weather", headers=_auth(token), json={})
    assert resp.status_code == 403, resp.text


def test_sync_weather_404s_for_unknown_estate(client, db_session, monkeypatch):
    _install_fake_nasa(monkeypatch)
    token = _admin_token(client)
    resp = client.post("/api/estates/4242/sync-weather", headers=_auth(token), json={})
    assert resp.status_code == 404, resp.text


def test_sync_weather_surfaces_ingestion_failure_as_502(client, db_session, monkeypatch):
    from app.api import routes_estate
    from app.services.nasa_power_ingestion import NasaPowerIngestionError

    estate = _make_estate(db_session)

    def _boom(db, estate, start_date, end_date, parameters=None, use_cache=True):
        raise NasaPowerIngestionError("NASA POWER unreachable")

    monkeypatch.setattr(routes_estate, "ingest_nasa_power_range", _boom)
    token = _admin_token(client)

    resp = client.post(f"/api/estates/{estate.id}/sync-weather", headers=_auth(token), json={})
    assert resp.status_code == 502, resp.text
    assert "unreachable" in resp.json()["detail"]


def test_sync_weather_defaults_to_a_lag_aware_window(client, db_session, monkeypatch):
    """
    The default window must sit inside the range NASA POWER can actually serve.
    Its hourly RE data lags real time by months, so defaulting to "recent days"
    would silently ingest nothing but fill values.
    """
    from app.core.config import settings

    estate = _make_estate(db_session)
    _install_fake_nasa(monkeypatch)
    token = _admin_token(client)

    resp = client.post(f"/api/estates/{estate.id}/sync-weather", headers=_auth(token), json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    start = date.fromisoformat(body["start_date"])
    end = date.fromisoformat(body["end_date"])
    assert start <= end
    assert (end - start).days == 3
    # Back-dated by the configured latency, and never in the future.
    assert (date.today() - end).days >= settings.nasa_power_data_lag_days
    assert end <= date.today()


def test_sync_weather_reports_when_no_irradiance_is_available(client, db_session, monkeypatch):
    """All-fill window must produce an explicit warning, not a silent empty chart."""
    estate = _make_estate(db_session)
    _install_fake_nasa(monkeypatch, ghi=None)  # every reading is a fill value
    token = _admin_token(client)

    resp = client.post(f"/api/estates/{estate.id}/sync-weather", headers=_auth(token), json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["records_written"] == FAKE_OBSERVATION_COUNT
    assert body["hours_with_ghi"] == 0
    assert body["hours_missing_ghi"] == FAKE_OBSERVATION_COUNT
    assert body["generation_estimates_written"] == 0
    assert body["warning"] and "lags" in body["warning"]


def test_sync_weather_reports_partial_irradiance_coverage(client, db_session, monkeypatch):
    """Nighttime hours are legitimately missing — warn without alarming."""
    estate = _make_estate(db_session)
    _install_fake_nasa(monkeypatch, ghi=500.0, missing_every=2)
    token = _admin_token(client)

    resp = client.post(f"/api/estates/{estate.id}/sync-weather", headers=_auth(token), json={})
    body = resp.json()

    assert body["hours_with_ghi"] == FAKE_OBSERVATION_COUNT // 2
    assert body["hours_missing_ghi"] == FAKE_OBSERVATION_COUNT // 2
    assert body["generation_estimates_written"] == FAKE_OBSERVATION_COUNT // 2
    assert body["warning"] and "no irradiance reading" in body["warning"]