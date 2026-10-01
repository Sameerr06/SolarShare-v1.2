"""
Tests for app/services/electricity_ingestion.py: full acquire -> parse ->
validate/convert -> persist pipeline, run against the local SYNTHETIC
fixture (tests/fixtures/sample_electricity_hourly_fixture.tsf) — NOT the
real Zenodo dataset, which could not be downloaded in this environment.
"""

import os

from app.models.public_load import PublicLoadObservation, PublicLoadSeries
from app.services.electricity_ingestion import ingest_electricity_dataset

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
FIXTURE_PATH = os.path.join(FIXTURE_DIR, "sample_electricity_hourly_fixture.tsf")
MISSING_FIXTURE_PATH = os.path.join(FIXTURE_DIR, "sample_electricity_hourly_missing_fixture.tsf")


def test_ingestion_persists_all_series(db_session):
    summary = ingest_electricity_dataset(db_session, local_path=FIXTURE_PATH)

    assert summary["series_parsed"] == 12
    assert summary["series_persisted"] == 12
    assert summary["series_rejected"] == 0

    series_rows = db_session.query(PublicLoadSeries).all()
    assert len(series_rows) == 12


def test_ingestion_persists_observations_with_correct_count(db_session):
    summary = ingest_electricity_dataset(db_session, local_path=FIXTURE_PATH)

    # 12 series x 72 hourly values each, per the fixture generation.
    assert summary["observations_persisted"] == 12 * 72

    obs_rows = db_session.query(PublicLoadObservation).all()
    assert len(obs_rows) == 12 * 72


def test_ingestion_reports_locked_unit_labels(db_session):
    summary = ingest_electricity_dataset(db_session, local_path=FIXTURE_PATH)
    assert summary["source_unit"] == "Hourly average electricity demand in kW."
    assert summary["internal_unit"] == "Hourly energy consumption in kWh."
    assert summary["frequency"] == "hourly"


def test_ingestion_reports_source_doi_and_name(db_session):
    summary = ingest_electricity_dataset(db_session, local_path=FIXTURE_PATH)
    assert summary["source_doi"] == "10.5281/zenodo.4656140"
    assert "Electricity Hourly Dataset" in summary["source_name"]


def test_persisted_series_carries_full_provenance(db_session):
    ingest_electricity_dataset(db_session, local_path=FIXTURE_PATH)
    row = db_session.query(PublicLoadSeries).filter(PublicLoadSeries.series_name == "T1").first()

    assert row is not None
    assert row.source_doi == "10.5281/zenodo.4656140"
    assert "zenodo.org" in row.source_url
    assert row.source_unit_description == "Hourly average electricity demand in kW."
    assert row.is_public_proxy is True
    assert "proxy" in row.provenance_label.lower()
    assert "not actual coimbatore" in row.provenance_label.lower()
    assert row.frequency == "hourly"
    assert row.value_count == 72
    assert row.retrieved_at is not None


def test_persisted_observation_stores_source_and_derived_values_separately(db_session):
    ingest_electricity_dataset(db_session, local_path=FIXTURE_PATH)
    series_row = db_session.query(PublicLoadSeries).filter(PublicLoadSeries.series_name == "T1").first()
    obs = (
        db_session.query(PublicLoadObservation)
        .filter(PublicLoadObservation.series_id == series_row.id)
        .order_by(PublicLoadObservation.timestamp_local)
        .first()
    )

    assert obs.hourly_average_kw is not None
    assert obs.energy_kwh is not None
    assert obs.hourly_average_kw == obs.energy_kwh  # numerically equal at interval_hours=1.0
    assert obs.interval_hours == 1.0


def test_persisted_observation_timestamps_are_hourly_and_sequential(db_session):
    ingest_electricity_dataset(db_session, local_path=FIXTURE_PATH)
    series_row = db_session.query(PublicLoadSeries).filter(PublicLoadSeries.series_name == "T1").first()
    obs_rows = (
        db_session.query(PublicLoadObservation)
        .filter(PublicLoadObservation.series_id == series_row.id)
        .order_by(PublicLoadObservation.timestamp_local)
        .all()
    )
    assert len(obs_rows) == 72
    for i in range(len(obs_rows) - 1):
        delta = obs_rows[i + 1].timestamp_local - obs_rows[i].timestamp_local
        assert delta.total_seconds() == 3600.0


def test_re_ingestion_upserts_not_duplicates(db_session):
    ingest_electricity_dataset(db_session, local_path=FIXTURE_PATH)
    ingest_electricity_dataset(db_session, local_path=FIXTURE_PATH)

    series_rows = db_session.query(PublicLoadSeries).all()
    obs_rows = db_session.query(PublicLoadObservation).all()
    assert len(series_rows) == 12  # not 24
    assert len(obs_rows) == 12 * 72  # not doubled


def test_ingestion_with_missing_values_persists_none_not_zero(db_session):
    summary = ingest_electricity_dataset(db_session, local_path=MISSING_FIXTURE_PATH)
    assert summary["records_missing_value"] == 3

    series_row = db_session.query(PublicLoadSeries).filter(PublicLoadSeries.series_name == "T1").first()
    obs_rows = (
        db_session.query(PublicLoadObservation)
        .filter(PublicLoadObservation.series_id == series_row.id)
        .order_by(PublicLoadObservation.timestamp_local)
        .all()
    )
    kw_values = [o.hourly_average_kw for o in obs_rows]
    assert kw_values == [10.5, None, 12.3, 0.0, 15.7, None]
    kwh_values = [o.energy_kwh for o in obs_rows]
    assert kwh_values == [10.5, None, 12.3, 0.0, 15.7, None]


def test_ingestion_resolves_path_from_settings_when_not_passed_explicitly(db_session, monkeypatch):
    """
    Confirms ELECTRICITY_DATASET_LOCAL_PATH (settings.electricity_dataset_local_path)
    is actually used when ingest_electricity_dataset() is called WITHOUT an
    explicit local_path argument -- this is exactly how it will be invoked
    against the real dataset path on the user's machine.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "electricity_dataset_local_path", FIXTURE_PATH)
    summary = ingest_electricity_dataset(db_session)  # no local_path argument passed
    assert summary["series_persisted"] == 12


def test_ingestion_raises_clear_error_for_missing_local_file(db_session, monkeypatch):
    from app.integrations.electricity_dataset import ElectricityDatasetAcquisitionError
    from app.core.config import settings

    # Ensure no fallback to a real network fetch of zenodo.org happens in
    # this test — force both the local path and the source URL to be
    # unusable so acquisition fails deterministically and fast.
    monkeypatch.setattr(settings, "electricity_dataset_local_path", "")
    monkeypatch.setattr(settings, "electricity_dataset_source_url", "")

    try:
        ingest_electricity_dataset(db_session, local_path="/nonexistent/path/does_not_exist.tsf")
        assert False, "expected ElectricityDatasetAcquisitionError"
    except ElectricityDatasetAcquisitionError:
        pass
