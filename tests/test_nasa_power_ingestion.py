from datetime import date, datetime, timezone

import pytest

from app.integrations.nasa_power import NasaPowerRequestError
from app.models.estate import Estate
from app.models.weather import NasaPowerCache, SolarGenerationEstimate, WeatherObservation
from app.services import nasa_power_ingestion as ingestion_module
from app.services.nasa_power_ingestion import (
    NasaPowerIngestionError,
    ingest_nasa_power_range,
)


def _make_estate(db_session):
    estate = Estate(name="Coimbatore Demo Estate", latitude=11.0168, longitude=76.9558)
    db_session.add(estate)
    db_session.commit()
    db_session.refresh(estate)
    return estate


def _fake_raw_response():
    return {
        "properties": {
            "parameter": {
                "ALLSKY_SFC_SW_DWN": {"2024010100": 0.0, "2024010101": 300.0},
                "T2M": {"2024010100": 23.0, "2024010101": 24.0},
                "RH2M": {"2024010100": 80.0, "2024010101": 78.0},
                "WS10M": {"2024010100": 2.1, "2024010101": 2.4},
            }
        }
    }


def test_ingestion_persists_weather_observations(db_session, monkeypatch):
    estate = _make_estate(db_session)
    monkeypatch.setattr(ingestion_module, "fetch_nasa_power", lambda params: _fake_raw_response())

    result = ingest_nasa_power_range(db_session, estate, date(2024, 1, 1), date(2024, 1, 1))

    assert result["records_written"] == 2
    assert result["data_status"] == "LIVE"
    assert result["cache_hit"] is False

    observations = db_session.query(WeatherObservation).filter(WeatherObservation.estate_id == estate.id).all()
    assert len(observations) == 2
    obs_by_hour = {o.timestamp.hour: o for o in observations}
    assert obs_by_hour[1].allsky_sfc_sw_dwn == 300.0
    assert obs_by_hour[0].allsky_sfc_sw_dwn == 0.0
    assert obs_by_hour[1].t2m == 24.0
    assert obs_by_hour[1].timestamp.tzinfo is not None


def test_ingestion_records_full_provenance(db_session, monkeypatch):
    estate = _make_estate(db_session)
    monkeypatch.setattr(ingestion_module, "fetch_nasa_power", lambda params: _fake_raw_response())

    ingest_nasa_power_range(db_session, estate, date(2024, 1, 1), date(2024, 1, 1))
    obs = db_session.query(WeatherObservation).first()

    assert obs.source_name == "NASA POWER"
    assert obs.source_type == "NASA_POWER"
    assert obs.latitude == 11.0168
    assert obs.longitude == 76.9558
    assert obs.community == "RE"
    assert "ALLSKY_SFC_SW_DWN" in obs.parameters_requested
    assert obs.time_standard == "UTC"
    assert obs.retrieved_at is not None
    assert obs.data_status == "LIVE"


def test_ingestion_writes_cache_entry(db_session, monkeypatch):
    estate = _make_estate(db_session)
    monkeypatch.setattr(ingestion_module, "fetch_nasa_power", lambda params: _fake_raw_response())

    ingest_nasa_power_range(db_session, estate, date(2024, 1, 1), date(2024, 1, 1))

    cache_entries = db_session.query(NasaPowerCache).all()
    assert len(cache_entries) == 1
    assert cache_entries[0].latitude == 11.0168
    assert cache_entries[0].longitude == 76.9558


def test_second_ingestion_call_uses_cache_not_live_fetch(db_session, monkeypatch):
    estate = _make_estate(db_session)
    call_count = {"n": 0}

    def fake_fetch(params):
        call_count["n"] += 1
        return _fake_raw_response()

    monkeypatch.setattr(ingestion_module, "fetch_nasa_power", fake_fetch)

    ingest_nasa_power_range(db_session, estate, date(2024, 1, 1), date(2024, 1, 1))
    assert call_count["n"] == 1

    result2 = ingest_nasa_power_range(db_session, estate, date(2024, 1, 1), date(2024, 1, 1))
    assert call_count["n"] == 1  # not called again — cache hit
    assert result2["cache_hit"] is True
    assert result2["data_status"] == "CACHED"


def test_re_ingestion_upserts_not_duplicates(db_session, monkeypatch):
    estate = _make_estate(db_session)
    monkeypatch.setattr(ingestion_module, "fetch_nasa_power", lambda params: _fake_raw_response())

    ingest_nasa_power_range(db_session, estate, date(2024, 1, 1), date(2024, 1, 1), use_cache=False)
    ingest_nasa_power_range(db_session, estate, date(2024, 1, 1), date(2024, 1, 1), use_cache=False)

    observations = db_session.query(WeatherObservation).filter(WeatherObservation.estate_id == estate.id).all()
    assert len(observations) == 2  # still just 2 hourly rows, not 4


def test_live_failure_falls_back_to_cache(db_session, monkeypatch):
    estate = _make_estate(db_session)

    # First call succeeds and populates the cache.
    monkeypatch.setattr(ingestion_module, "fetch_nasa_power", lambda params: _fake_raw_response())
    ingest_nasa_power_range(db_session, estate, date(2024, 1, 1), date(2024, 1, 1))

    # Second call: force live fetch to fail; should fall back to cache.
    def failing_fetch(params):
        raise NasaPowerRequestError("simulated outage")

    monkeypatch.setattr(ingestion_module, "fetch_nasa_power", failing_fetch)
    result = ingest_nasa_power_range(db_session, estate, date(2024, 1, 1), date(2024, 1, 1), use_cache=False)

    assert result["data_status"] == "CACHED"
    assert result["cache_hit"] is True


def test_live_failure_with_no_cache_raises_ingestion_error(db_session, monkeypatch):
    estate = _make_estate(db_session)

    def failing_fetch(params):
        raise NasaPowerRequestError("simulated outage")

    monkeypatch.setattr(ingestion_module, "fetch_nasa_power", failing_fetch)

    with pytest.raises(NasaPowerIngestionError):
        ingest_nasa_power_range(db_session, estate, date(2024, 1, 1), date(2024, 1, 1))


def test_invalid_response_raises_ingestion_error(db_session, monkeypatch):
    estate = _make_estate(db_session)
    monkeypatch.setattr(ingestion_module, "fetch_nasa_power", lambda params: {"bad": "response"})

    with pytest.raises(NasaPowerIngestionError):
        ingest_nasa_power_range(db_session, estate, date(2024, 1, 1), date(2024, 1, 1))
