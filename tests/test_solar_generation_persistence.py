from datetime import datetime, timezone

from app.models.config import PVConfig
from app.models.estate import Estate
from app.models.weather import SolarGenerationEstimate, WeatherObservation
from app.services.solar_generation import estimate_for_observation


def _make_estate_and_pv_config(db_session):
    estate = Estate(name="Coimbatore Demo Estate", latitude=11.0168, longitude=76.9558)
    db_session.add(estate)
    db_session.commit()
    db_session.refresh(estate)

    pv_config = PVConfig(
        estate_id=estate.id,
        capacity_kw=500.0,
        efficiency=0.20,
        performance_ratio=0.80,
        effective_from=datetime.now(timezone.utc),
    )
    db_session.add(pv_config)
    db_session.commit()
    db_session.refresh(pv_config)
    return estate, pv_config


def test_estimate_persists_for_valid_observation(db_session):
    estate, pv_config = _make_estate_and_pv_config(db_session)
    obs = WeatherObservation(
        estate_id=estate.id,
        timestamp=datetime(2024, 1, 1, 6, tzinfo=timezone.utc),
        allsky_sfc_sw_dwn=1000.0,
        source_url="https://power.larc.nasa.gov/api/temporal/hourly/point",
        latitude=estate.latitude,
        longitude=estate.longitude,
        parameters_requested="ALLSKY_SFC_SW_DWN",
        retrieved_at=datetime.now(timezone.utc),
    )
    db_session.add(obs)
    db_session.commit()
    db_session.refresh(obs)

    result = estimate_for_observation(db_session, obs, pv_config, persist=True)

    assert result is not None
    assert result.estimated_kwh == 400.0  # MODEL B: 1.0 * 500 * 0.80 (efficiency not multiplied in)
    stored = db_session.query(SolarGenerationEstimate).filter(
        SolarGenerationEstimate.estate_id == estate.id
    ).first()
    assert stored is not None
    assert stored.estimated_kwh == 400.0
    assert stored.weather_observation_id == obs.id
    assert stored.pv_config_id == pv_config.id


def test_estimate_skipped_for_missing_ghi_reading(db_session):
    estate, pv_config = _make_estate_and_pv_config(db_session)
    obs = WeatherObservation(
        estate_id=estate.id,
        timestamp=datetime(2024, 1, 1, 6, tzinfo=timezone.utc),
        allsky_sfc_sw_dwn=None,  # missing/fill-value reading
        source_url="https://power.larc.nasa.gov/api/temporal/hourly/point",
        latitude=estate.latitude,
        longitude=estate.longitude,
        parameters_requested="ALLSKY_SFC_SW_DWN",
        retrieved_at=datetime.now(timezone.utc),
    )
    db_session.add(obs)
    db_session.commit()
    db_session.refresh(obs)

    result = estimate_for_observation(db_session, obs, pv_config, persist=True)

    assert result is None
    assert db_session.query(SolarGenerationEstimate).count() == 0
