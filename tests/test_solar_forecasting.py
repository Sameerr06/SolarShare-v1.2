"""
Unit and integration tests for Prophet solar PV generation forecasting service and API endpoint.
"""

from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.config import PVConfig
from app.models.estate import Estate
from app.models.weather import SolarGenerationEstimate, WeatherObservation
from app.schemas.forecasting import SolarForecastResponse
from app.services.solar_forecasting import (
    generate_solar_forecast,
    prepare_training_data,
    train_prophet_model,
)


def _seed_historical_solar_data(db_session, estate_id: int = 1, days: int = 7):
    """Helper to seed mock weather observations and solar generation estimates."""
    estate = db_session.get(Estate, estate_id)
    if not estate:
        estate = Estate(id=estate_id, name="Test Estate", latitude=11.0168, longitude=76.9558)
        db_session.add(estate)
        db_session.commit()

    pv_config = (
        db_session.query(PVConfig)
        .filter(PVConfig.estate_id == estate_id, PVConfig.is_active == True)
        .first()
    )
    if not pv_config:
        pv_config = PVConfig(
            estate_id=estate_id,
            capacity_kw=500.0,
            efficiency=0.20,
            performance_ratio=0.80,
            effective_from=datetime.now(timezone.utc),
            is_active=True,
        )
        db_session.add(pv_config)
        db_session.commit()

    base_time = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    # Bell curve factor by hour of day
    hourly_factors = [
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
        0.1, 0.3, 0.6, 0.8, 0.95, 1.0,
        0.95, 0.8, 0.6, 0.3, 0.1, 0.0,
        0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
    ]

    for d in range(days):
        for h in range(24):
            ts = base_time + timedelta(days=d, hours=h)
            factor = hourly_factors[h]
            ghi = round(1000.0 * factor, 1)
            kwh = round(400.0 * factor, 2)  # 500 kW * 0.8 PR * factor

            w_obs = WeatherObservation(
                estate_id=estate_id,
                timestamp=ts,
                allsky_sfc_sw_dwn=ghi,
                t2m=28.0,
                rh2m=60.0,
                ws10m=2.0,
                source_name="NASA POWER",
                source_type="NASA_POWER",
                source_url="https://power.larc.nasa.gov",
                latitude=11.0168,
                longitude=76.9558,
                community="RE",
                parameters_requested="ALLSKY_SFC_SW_DWN",
                time_standard="UTC",
                retrieved_at=base_time,
                units="W/m^2",
                data_status="LIVE",
            )
            db_session.add(w_obs)
            db_session.flush()

            gen_est = SolarGenerationEstimate(
                estate_id=estate_id,
                timestamp=ts,
                estimated_kwh=kwh,
                pv_config_id=pv_config.id,
                weather_observation_id=w_obs.id,
            )
            db_session.add(gen_est)

    db_session.commit()


def test_prepare_training_data_structure(db_session):
    _seed_historical_solar_data(db_session, estate_id=1, days=3)
    df = prepare_training_data(db_session, estate_id=1)

    assert not df.empty
    assert list(df.columns) == ["ds", "y"]
    assert len(df) == 3 * 24  # 72 records


def test_train_prophet_model(db_session):
    _seed_historical_solar_data(db_session, estate_id=1, days=3)
    df = prepare_training_data(db_session, estate_id=1)
    model = train_prophet_model(df)

    assert model is not None
    assert model.daily_seasonality is True


def test_solar_forecast_generation_and_24h_horizon(db_session):
    _seed_historical_solar_data(db_session, estate_id=1, days=3)
    response = generate_solar_forecast(db_session, estate_id=1, hours=24)

    assert isinstance(response, SolarForecastResponse)
    assert response.estate_id == 1
    assert response.forecast_period_hours == 24
    assert len(response.forecast_data) == 24
    assert response.total_generation_forecast_kwh >= 0.0
    assert response.peak_generation_kw >= 0.0


def test_solar_forecast_custom_horizon(db_session):
    _seed_historical_solar_data(db_session, estate_id=1, days=3)
    response = generate_solar_forecast(db_session, estate_id=1, hours=48)

    assert response.forecast_period_hours == 48
    assert len(response.forecast_data) == 48


def test_solar_forecast_non_negative_output(db_session):
    _seed_historical_solar_data(db_session, estate_id=1, days=3)
    response = generate_solar_forecast(db_session, estate_id=1, hours=24)

    for pt in response.forecast_data:
        assert pt.predicted_value_kw >= 0.0, f"Negative prediction found: {pt.predicted_value_kw}"
        assert pt.lower_bound_kw >= 0.0, f"Negative lower bound found: {pt.lower_bound_kw}"
        assert pt.upper_bound_kw >= 0.0, f"Negative upper bound found: {pt.upper_bound_kw}"


def test_solar_forecast_uncertainty_bounds(db_session):
    _seed_historical_solar_data(db_session, estate_id=1, days=3)
    response = generate_solar_forecast(db_session, estate_id=1, hours=24)

    for pt in response.forecast_data:
        assert pt.lower_bound_kw <= pt.predicted_value_kw, (
            f"Lower bound {pt.lower_bound_kw} > predicted {pt.predicted_value_kw}"
        )
        assert pt.predicted_value_kw <= pt.upper_bound_kw, (
            f"Predicted {pt.predicted_value_kw} > upper bound {pt.upper_bound_kw}"
        )


def test_solar_forecast_provenance_and_real_status(db_session):
    _seed_historical_solar_data(db_session, estate_id=1, days=3)
    response = generate_solar_forecast(db_session, estate_id=1, hours=24)

    assert response.is_demo is False
    assert response.model_name == "Prophet"
    assert response.training_record_count == 72
    assert response.training_start_date is not None
    assert response.training_end_date is not None
    assert response.generated_at is not None
    assert "Prophet solar PV generation forecast" in response.explanatory_note


def test_get_solar_forecast_api_endpoint(db_session):
    _seed_historical_solar_data(db_session, estate_id=1, days=3)
    client = TestClient(app)

    res = client.get("/api/forecasting/solar?estate_id=1&hours=24")
    assert res.status_code == 200

    payload = res.json()
    assert payload["estate_id"] == 1
    assert payload["forecast_period_hours"] == 24
    assert payload["is_demo"] is False
    assert payload["model_name"] == "Prophet"
    assert payload["training_record_count"] >= 72
    assert len(payload["forecast_data"]) == 24
    assert payload["total_generation_forecast_kwh"] >= 0.0
