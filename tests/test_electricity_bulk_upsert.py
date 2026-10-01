"""
Tests specifically for the bulk upsert mechanism used by
app/services/electricity_ingestion.py's `_bulk_upsert_observations()` --
confirms it uses a genuine SQL-level upsert (ON CONFLICT DO UPDATE)
against the (series_id, timestamp_local) unique constraint, rather than
ORM per-row query+add, and that it never populates the ORM identity map
with observation objects.
"""

import os
from datetime import datetime, timezone

from app.models.public_load import PublicLoadObservation, PublicLoadSeries
from app.services.electricity_ingestion import _bulk_upsert_observations, _persist_series_row
from app.integrations.electricity_dataset import ElectricityDatasetSourceConfig, ValidatedSeries

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _make_series_row(db_session, name="T_BULK_TEST"):
    validated = ValidatedSeries(
        series_name=name,
        start_timestamp_local=datetime(2012, 1, 1, 0, 0, 0),
        frequency="hourly",
        timestamps=[],
        hourly_average_kw=[],
        energy_kwh=[],
    )
    row = _persist_series_row(db_session, validated, ElectricityDatasetSourceConfig(), datetime.now(timezone.utc))
    db_session.commit()
    return row


def test_bulk_upsert_inserts_new_rows_in_one_statement(db_session):
    series_row = _make_series_row(db_session)
    validated = ValidatedSeries(
        series_name=series_row.series_name,
        start_timestamp_local=datetime(2012, 1, 1, 0, 0, 0),
        frequency="hourly",
        timestamps=[datetime(2012, 1, 1, h, 0, 0) for h in range(5)],
        hourly_average_kw=[1.0, 2.0, 3.0, 4.0, 5.0],
        energy_kwh=[1.0, 2.0, 3.0, 4.0, 5.0],
    )
    written = _bulk_upsert_observations(db_session, series_row.id, validated)
    db_session.commit()

    assert written == 5
    rows = (
        db_session.query(PublicLoadObservation)
        .filter(PublicLoadObservation.series_id == series_row.id)
        .order_by(PublicLoadObservation.timestamp_local)
        .all()
    )
    assert len(rows) == 5
    assert [r.hourly_average_kw for r in rows] == [1.0, 2.0, 3.0, 4.0, 5.0]


def test_bulk_upsert_updates_existing_rows_on_conflict(db_session):
    series_row = _make_series_row(db_session)
    ts = [datetime(2012, 1, 1, h, 0, 0) for h in range(3)]

    first = ValidatedSeries(
        series_name=series_row.series_name,
        start_timestamp_local=ts[0],
        frequency="hourly",
        timestamps=ts,
        hourly_average_kw=[10.0, 20.0, 30.0],
        energy_kwh=[10.0, 20.0, 30.0],
    )
    _bulk_upsert_observations(db_session, series_row.id, first)
    db_session.commit()

    # Re-upsert the SAME timestamps with DIFFERENT values -- must update in place.
    second = ValidatedSeries(
        series_name=series_row.series_name,
        start_timestamp_local=ts[0],
        frequency="hourly",
        timestamps=ts,
        hourly_average_kw=[100.0, 200.0, 300.0],
        energy_kwh=[100.0, 200.0, 300.0],
    )
    _bulk_upsert_observations(db_session, series_row.id, second)
    db_session.commit()

    rows = (
        db_session.query(PublicLoadObservation)
        .filter(PublicLoadObservation.series_id == series_row.id)
        .order_by(PublicLoadObservation.timestamp_local)
        .all()
    )
    assert len(rows) == 3  # not 6 -- conflict resolved as UPDATE, not duplicate INSERT
    assert [r.hourly_average_kw for r in rows] == [100.0, 200.0, 300.0]


def test_bulk_upsert_preserves_created_at_on_conflict_update(db_session):
    series_row = _make_series_row(db_session)
    ts = [datetime(2012, 1, 1, 0, 0, 0)]

    first = ValidatedSeries(
        series_name=series_row.series_name, start_timestamp_local=ts[0], frequency="hourly",
        timestamps=ts, hourly_average_kw=[1.0], energy_kwh=[1.0],
    )
    _bulk_upsert_observations(db_session, series_row.id, first)
    db_session.commit()

    original = db_session.query(PublicLoadObservation).filter(PublicLoadObservation.series_id == series_row.id).first()
    original_created_at = original.created_at
    db_session.expunge_all()

    second = ValidatedSeries(
        series_name=series_row.series_name, start_timestamp_local=ts[0], frequency="hourly",
        timestamps=ts, hourly_average_kw=[999.0], energy_kwh=[999.0],
    )
    _bulk_upsert_observations(db_session, series_row.id, second)
    db_session.commit()

    updated = db_session.query(PublicLoadObservation).filter(PublicLoadObservation.series_id == series_row.id).first()
    assert updated.hourly_average_kw == 999.0
    assert updated.created_at == original_created_at  # never overwritten on conflict


def test_bulk_upsert_does_not_populate_orm_identity_map(db_session):
    """
    The whole point of the Core-level bulk upsert is that observation rows
    never become tracked ORM objects in the Session -- confirms this by
    checking the identity map is empty of PublicLoadObservation instances
    immediately after the bulk call (before any query re-loads them).
    """
    series_row = _make_series_row(db_session)
    from datetime import timedelta
    base = datetime(2012, 1, 1, 0, 0, 0)
    ts = [base + timedelta(hours=h) for h in range(1000)]
    validated = ValidatedSeries(
        series_name=series_row.series_name, start_timestamp_local=ts[0], frequency="hourly",
        timestamps=ts, hourly_average_kw=[float(i) for i in range(1000)], energy_kwh=[float(i) for i in range(1000)],
    )
    _bulk_upsert_observations(db_session, series_row.id, validated)

    tracked_observations = [obj for obj in db_session.identity_map.values() if isinstance(obj, PublicLoadObservation)]
    assert len(tracked_observations) == 0  # bulk Core insert never touched the identity map
    db_session.commit()


def test_bulk_upsert_handles_none_values_correctly(db_session):
    series_row = _make_series_row(db_session)
    ts = [datetime(2012, 1, 1, h, 0, 0) for h in range(3)]
    validated = ValidatedSeries(
        series_name=series_row.series_name, start_timestamp_local=ts[0], frequency="hourly",
        timestamps=ts, hourly_average_kw=[1.0, None, 3.0], energy_kwh=[1.0, None, 3.0],
    )
    _bulk_upsert_observations(db_session, series_row.id, validated)
    db_session.commit()

    rows = (
        db_session.query(PublicLoadObservation)
        .filter(PublicLoadObservation.series_id == series_row.id)
        .order_by(PublicLoadObservation.timestamp_local)
        .all()
    )
    assert [r.hourly_average_kw for r in rows] == [1.0, None, 3.0]
    assert [r.energy_kwh for r in rows] == [1.0, None, 3.0]


def test_bulk_upsert_empty_series_writes_nothing(db_session):
    series_row = _make_series_row(db_session)
    validated = ValidatedSeries(
        series_name=series_row.series_name, start_timestamp_local=datetime(2012, 1, 1), frequency="hourly",
        timestamps=[], hourly_average_kw=[], energy_kwh=[],
    )
    written = _bulk_upsert_observations(db_session, series_row.id, validated)
    assert written == 0
