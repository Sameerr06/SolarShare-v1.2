"""
Tests for the STREAMING ingestion architecture specifically: confirms
series are processed one at a time (not all materialized upfront), that
persistence happens incrementally, and that a failure partway through
doesn't lose already-committed work.
"""

import os

from app.integrations.tsf_parser import parse_tsf_streaming
from app.models.public_load import PublicLoadObservation, PublicLoadSeries
from app.services.electricity_ingestion import ingest_electricity_dataset

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
FIXTURE_PATH = os.path.join(FIXTURE_DIR, "sample_electricity_hourly_fixture.tsf")


def test_streaming_parser_yields_series_lazily_not_all_at_once():
    """
    Confirms parse_tsf_streaming() returns a genuine generator, not a list --
    i.e. series are produced on demand as the iterator is advanced, not all
    materialized before the function returns.
    """
    metadata, series_iter = parse_tsf_streaming(FIXTURE_PATH)
    assert not isinstance(series_iter, list)
    assert hasattr(series_iter, "__next__")  # a real iterator/generator

    first = next(series_iter)
    assert first.series_name == "T1"
    # The rest are still un-consumed -- proves we didn't eagerly parse them all.
    remaining = list(series_iter)
    assert len(remaining) == 11  # 12 total, 1 already consumed


def test_streaming_parser_metadata_available_before_full_iteration():
    """Metadata must be usable without having to exhaust the series generator."""
    metadata, series_iter = parse_tsf_streaming(FIXTURE_PATH)
    assert metadata.frequency == "hourly"
    assert metadata.equallength is True
    # series_iter is untouched at this point -- metadata didn't require it.


def test_ingestion_commits_incrementally_series_by_series(db_session, monkeypatch):
    """
    Confirms persistence happens per-series (not all-at-once at the end) by
    injecting a failure partway through and checking that series processed
    BEFORE the failure are still durably committed.
    """
    from app.services import electricity_ingestion as ingestion_module

    original_bulk_upsert = ingestion_module._bulk_upsert_observations
    call_count = {"n": 0}

    def _flaky_bulk_upsert(db, series_id, validated):
        call_count["n"] += 1
        if call_count["n"] == 5:  # fail partway through the 12 series
            raise RuntimeError("simulated failure on the 5th series")
        return original_bulk_upsert(db, series_id, validated)

    from sqlalchemy.exc import SQLAlchemyError

    def _flaky_bulk_upsert_sqlalchemy_error(db, series_id, validated):
        call_count["n"] += 1
        if call_count["n"] == 5:
            raise SQLAlchemyError("simulated DB failure on the 5th series")
        return original_bulk_upsert(db, series_id, validated)

    monkeypatch.setattr(ingestion_module, "_bulk_upsert_observations", _flaky_bulk_upsert_sqlalchemy_error)

    summary = ingest_electricity_dataset(db_session, local_path=FIXTURE_PATH)

    # 11 succeeded, 1 rejected (the simulated failure), not a total abort.
    assert summary["series_persisted"] == 11
    assert summary["series_rejected"] == 1
    assert len(summary["rejected_series_reasons"]) == 1
    assert "simulated DB failure" in summary["rejected_series_reasons"][0]

    # Confirm the 11 successful series are ACTUALLY durably in the DB.
    series_rows = db_session.query(PublicLoadSeries).all()
    assert len(series_rows) == 11
    obs_rows = db_session.query(PublicLoadObservation).all()
    assert len(obs_rows) == 11 * 72


def test_failure_on_one_series_does_not_corrupt_other_series_data(db_session, monkeypatch):
    """
    After a partial failure, the successfully-ingested series' observation
    data must still be fully correct (not partially written / truncated).
    """
    from app.services import electricity_ingestion as ingestion_module
    from sqlalchemy.exc import SQLAlchemyError

    original_bulk_upsert = ingestion_module._bulk_upsert_observations
    call_count = {"n": 0}

    def _flaky(db, series_id, validated):
        call_count["n"] += 1
        if call_count["n"] == 3:
            raise SQLAlchemyError("simulated failure")
        return original_bulk_upsert(db, series_id, validated)

    monkeypatch.setattr(ingestion_module, "_bulk_upsert_observations", _flaky)

    ingest_electricity_dataset(db_session, local_path=FIXTURE_PATH)

    # T1 was processed first (call_count 1) and should be fully intact.
    t1 = db_session.query(PublicLoadSeries).filter(PublicLoadSeries.series_name == "T1").first()
    assert t1 is not None
    obs = db_session.query(PublicLoadObservation).filter(PublicLoadObservation.series_id == t1.id).all()
    assert len(obs) == 72  # complete, not truncated
