"""
Unit and integration tests for Prophet tenant load forecasting service and API endpoint.
"""

import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone
import pytest

from app.models.tenant import Tenant
from app.models.public_load import PublicLoadSeries, PublicLoadObservation
from app.schemas.forecasting import TenantForecastResponse
from app.services import tenant_forecasting
from app.services.tenant_forecasting import (
    generate_tenant_forecast,
    prepare_tenant_training_data,
    train_tenant_prophet_model,
    get_series_for_tenant,
    load_model_from_cache,
    save_model_to_cache,
)


def _seed_historical_tenant_data(db_session, tenant_id: int = 1, series_name: str = "T258", hours_count: int = 48):
    """Helper to seed public load series, observations, and tenant mapping."""
    series = db_session.query(PublicLoadSeries).filter(PublicLoadSeries.series_name == series_name).first()
    if not series:
        series = PublicLoadSeries(
            series_name=series_name,
            start_timestamp_local=datetime(2012, 1, 1, 0, 0, 0),
            frequency="H",
            value_count=hours_count,
            source_name="Monash Electricity",
            source_doi="10.5281/zenodo.55648",
            source_url="https://zenodo.org",
            retrieved_at=datetime.now(),
            is_public_proxy=True,
            provenance_label="Public electricity-consumption dataset used as a tenant-load proxy.",
        )
        db_session.add(series)
        db_session.commit()
        db_session.refresh(series)

    # Seed observations with the :00:01 offset
    base_time = datetime(2012, 1, 1, 0, 0, 1)
    for h in range(hours_count):
        ts = base_time + timedelta(hours=h)
        obs = PublicLoadObservation(
            series_id=series.id,
            timestamp_local=ts,
            hourly_average_kw=15.0 + (h % 24) * 2.0,
            energy_kwh=15.0 + (h % 24) * 2.0,
            interval_hours=1.0,
        )
        db_session.add(obs)
    
    tenant = db_session.get(Tenant, tenant_id)
    if not tenant:
        tenant = Tenant(
            id=tenant_id,
            estate_id=1,
            name="Test Textile Manufacturer",
            profile_type="TEXTILE_MANUFACTURING",
            source_client_series_id=series_name,
        )
        db_session.add(tenant)
    db_session.commit()


def test_get_series_for_tenant_fallback():
    """Verify series mapping logic handles fallbacks when database entry is missing."""
    # Custom tenant mock
    class MockTenant:
        source_client_series_id = None
        profile_type = "FOOD_PROCESSING"

    tenant_food = MockTenant()
    assert get_series_for_tenant(2, tenant_food) == "T11"

    # Fully empty fallback (deterministic modulo fallback)
    assert get_series_for_tenant(1, None) == "T258"
    assert get_series_for_tenant(6, None) == "T3"
    assert get_series_for_tenant(7, None) == "T258"  # modulo wraparound


def test_prepare_tenant_training_data_normalization(db_session):
    """Verify prep loads correct observation count and rounds timestamps to hour boundary."""
    _seed_historical_tenant_data(db_session, tenant_id=1, series_name="T258", hours_count=48)
    df = prepare_tenant_training_data(db_session, "T258")

    assert not df.empty
    assert len(df) == 48
    # Assert columns ds and y are correct
    assert "ds" in df.columns
    assert "y" in df.columns
    # Check normalization: second should be 0
    first_ds = df["ds"].iloc[0]
    assert first_ds.second == 0
    assert first_ds.minute == 0
    assert first_ds.hour == 0


def test_prophet_model_training_and_serialization(db_session):
    """Verify training runs successfully and serialization writes/loads valid JSON cache."""
    _seed_historical_tenant_data(db_session, tenant_id=1, series_name="T258", hours_count=36)
    df = prepare_tenant_training_data(db_session, "T258")

    model = train_tenant_prophet_model(df)
    assert model is not None

    # Redirect MODELS_DIR to a temporary folder during the test
    with tempfile.TemporaryDirectory() as tmpdir:
        original_models_dir = tenant_forecasting.MODELS_DIR
        tenant_forecasting.MODELS_DIR = tmpdir
        try:
            # Save to temporary cache
            save_model_to_cache("T258", model)
            assert os.path.exists(os.path.join(tmpdir, "T258.json"))
            
            # Load from cache
            loaded_model = load_model_from_cache("T258")
            assert loaded_model is not None
            assert loaded_model.growth == "flat"
        finally:
            tenant_forecasting.MODELS_DIR = original_models_dir


def test_generate_tenant_forecast_output(db_session):
    """Verify service outputs valid response structure and clips negative bounds to zero."""
    _seed_historical_tenant_data(db_session, tenant_id=1, series_name="T258", hours_count=36)
    
    # Run service (this will trigger training on-the-fly since it's a test session and cache is empty/temp)
    # Redirect MODELS_DIR to prevent pollution
    with tempfile.TemporaryDirectory() as tmpdir:
        original_models_dir = tenant_forecasting.MODELS_DIR
        tenant_forecasting.MODELS_DIR = tmpdir
        try:
            start_time = datetime(2026, 8, 27, 12, 0, 0)
            res = generate_tenant_forecast(db_session, tenant_id=1, hours=24, start_time=start_time)
            
            assert isinstance(res, TenantForecastResponse)
            assert res.tenant_id == 1
            assert res.is_demo is False
            assert len(res.forecast_data) == 24
            assert res.explanatory_note is not None
            
            # Ensure bounds and non-negativity
            for point in res.forecast_data:
                assert point.predicted_value_kw >= 0.0
                assert point.lower_bound_kw >= 0.0
                assert point.lower_bound_kw <= point.predicted_value_kw
                assert point.predicted_value_kw <= point.upper_bound_kw
        finally:
            tenant_forecasting.MODELS_DIR = original_models_dir


def test_tenant_forecasting_api_endpoint(client, db_session, admin_auth):
    """Integration test: Verify the GET forecasting/tenants/{tenant_id} endpoint returns 200."""
    _seed_historical_tenant_data(db_session, tenant_id=1, series_name="T258", hours_count=36)

    # The `client` fixture points the API at the in-memory test database that
    # was just seeded, instead of the real `solarshare.db` file.
    assert client.get("/api/forecasting/tenants/1?hours=12").status_code == 401

    response = client.get("/api/forecasting/tenants/1?hours=12", headers=admin_auth)
    assert response.status_code == 200
    
    data = response.json()
    assert data["tenant_id"] == 1
    assert data["forecast_period_hours"] == 12
    # Since we seeded the database and have the models cached/trained, it should return is_demo=False
    assert data["is_demo"] is False
    assert len(data["forecast_data"]) == 12
    # A real model run must not carry a fallback reason.
    assert data["fallback_reason"] is None


# ---------------------------------------------------------------------------
# Degradation must be loud — see the equivalent note in
# tests/test_solar_forecasting.py. The tenant path previously degraded silently
# to a synthetic load curve, which is the worse failure of the two: a tenant
# would act on a demand number that no model ever produced.
# ---------------------------------------------------------------------------


def test_tenant_forecast_fallback_is_flagged_with_reason(db_session, tmp_path):
    from app.models.estate import Estate
    from app.models.enums import TenantProfileType
    from app.models.tenant import Tenant
    from app.services import tenant_forecasting

    estate = Estate(name="Fallback Estate", latitude=11.0168, longitude=76.9558)
    db_session.add(estate)
    db_session.commit()
    db_session.refresh(estate)

    tenant = Tenant(
        estate_id=estate.id,
        name="Unseeded Tenant",
        profile_type=TenantProfileType.TEXTILE_MANUFACTURING,
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    # Two conditions must both hold for training to fail, and the repo ships
    # real cached models in app/resources/models/ — so point MODELS_DIR at an
    # empty directory (cache miss) and leave PublicLoadObservation empty
    # (training impossible).
    original_models_dir = tenant_forecasting.MODELS_DIR
    tenant_forecasting.MODELS_DIR = tmp_path
    try:
        res = generate_tenant_forecast(db_session, tenant_id=tenant.id, hours=12)
    finally:
        tenant_forecasting.MODELS_DIR = original_models_dir

    assert res.is_demo is True
    assert res.model_name == "Prophet (Demo Fallback)"
    assert res.training_record_count == 0
    assert res.fallback_reason, "fallback_reason must be populated on the demo path"
    assert "FALLBACK DEMO CURVE" in res.explanatory_note
    assert "NOT A MODEL OUTPUT" in res.explanatory_note
    assert len(res.forecast_data) == 12


def test_tenant_forecast_fallback_reason_surfaces_over_http(
    client, db_session, make_tenant_token, tmp_path
):
    from app.services import tenant_forecasting

    token = make_tenant_token(1)
    headers = {"Authorization": f"Bearer {token}"}

    original_models_dir = tenant_forecasting.MODELS_DIR
    tenant_forecasting.MODELS_DIR = tmp_path
    try:
        res = client.get("/api/forecasting/tenants/1?hours=12", headers=headers)
    finally:
        tenant_forecasting.MODELS_DIR = original_models_dir

    assert res.status_code == 200
    payload = res.json()

    assert payload["is_demo"] is True
    assert payload["fallback_reason"]
    assert "NOT A MODEL OUTPUT" in payload["explanatory_note"]
