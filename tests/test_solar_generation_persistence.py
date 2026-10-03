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


# ---------------------------------------------------------------------------
# GET /api/solar/generation field provenance.
#
# This endpoint used to emit hardcoded placeholders (ghi=0.0, dni=0.0, dhi=0.0,
# poa=0.0, cell_temp=25.0, capacity=500.0, PR=0.80) alongside the one real
# figure, estimated_kwh. These cases pin the corrected contract: measured values
# come from the joined WeatherObservation/PVConfig rows, and anything this
# integration genuinely does not measure is null rather than a fabricated 0.
# ---------------------------------------------------------------------------


def _seed_generation_record(db_session, ghi=820.0, t2m=31.5):
    estate, pv_config = _make_estate_and_pv_config(db_session)
    obs = WeatherObservation(
        estate_id=estate.id,
        timestamp=datetime(2024, 1, 1, 6, tzinfo=timezone.utc),
        allsky_sfc_sw_dwn=ghi,
        t2m=t2m,
        source_url="https://power.larc.nasa.gov/api/temporal/hourly/point",
        latitude=estate.latitude,
        longitude=estate.longitude,
        parameters_requested="ALLSKY_SFC_SW_DWN,T2M",
        retrieved_at=datetime.now(timezone.utc),
    )
    db_session.add(obs)
    db_session.commit()
    db_session.refresh(obs)

    est = SolarGenerationEstimate(
        estate_id=estate.id,
        timestamp=datetime(2024, 1, 1, 6, tzinfo=timezone.utc),
        estimated_kwh=328.0,
        pv_config_id=pv_config.id,
        weather_observation_id=obs.id,
    )
    db_session.add(est)
    db_session.commit()
    return estate, pv_config, obs, est


def test_generation_endpoint_reports_measured_irradiance_and_config(client, db_session, admin_auth):
    estate, pv_config, obs, est = _seed_generation_record(db_session)

    resp = client.get("/api/solar/generation", params={"estate_id": estate.id}, headers=admin_auth)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_demo"] is False
    record = body["records"][0]

    # measured, joined from the WeatherObservation row
    assert record["ghi_wm2"] == 820.0
    assert record["ambient_temperature_c"] == 31.5

    # the stored estimate, plus the config row it was computed with
    assert record["pv_energy_kwh"] == 328.0
    assert record["capacity_kw"] == pv_config.capacity_kw == 500.0
    assert record["performance_ratio"] == pv_config.performance_ratio == 0.80

    # NOT measured by this integration -> null, never a fabricated 0.0
    assert record["dni_wm2"] is None
    assert record["dhi_wm2"] is None
    assert record["poa_irradiance_wm2"] is None

    # documented NOCT estimate, not a fixed 25.0
    expected_cell = round(31.5 + ((45.0 - 20.0) / 800.0) * 820.0, 2)
    assert record["cell_temperature_c"] == expected_cell
    assert record["cell_temperature_c"] != 25.0


def test_generation_endpoint_nulls_fields_when_weather_row_missing(client, db_session, admin_auth):
    """An orphaned estimate degrades to nulls, never to invented irradiance."""
    estate, pv_config, obs, est = _seed_generation_record(db_session)

    obs_id = est.weather_observation_id
    db_session.delete(obs)
    db_session.commit()

    resp = client.get("/api/solar/generation", params={"estate_id": estate.id}, headers=admin_auth)
    assert resp.status_code == 200, resp.text
    record = resp.json()["records"][0]

    assert record["ghi_wm2"] is None
    assert record["ambient_temperature_c"] is None
    assert record["cell_temperature_c"] is None
    # the estimate itself survives
    assert record["pv_energy_kwh"] == 328.0


def test_generation_endpoint_demo_fallback_is_flagged(client, admin_auth):
    resp = client.get("/api/solar/generation", headers=admin_auth)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_demo"] is True
    assert body["total_records"] == 24
    # the demo curve populates the illustrative irradiance columns; that is
    # precisely why it must stay flagged is_demo=True.
    assert body["records"][12]["ghi_wm2"] is not None
