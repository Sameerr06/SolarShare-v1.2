"""
Tests for app/services/load_profiling.py -- the 321->6 load-profile
selection methodology (v2, shape-aware).

Since the real 8.4M-row dataset only exists on the user's machine, these
tests seed a small set of SYNTHETIC series with deliberately distinct,
controllable hourly patterns (daytime-heavy, evening-heavy, flat, etc.)
covering multiple weeks so both weekday and weekend 24-hour shapes are
fully populated. This validates the pipeline's correctness and
determinism; it does not (and cannot, in this environment) validate the
real dataset's actual clustering outcome.
"""

import json
import math
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from app.models.estate import Estate
from app.models.public_load import PublicLoadObservation, PublicLoadSeries
from app.models.load_profile import PublicLoadSeriesProfile
from app.services.load_profiling import (
    LoadProfilingError,
    N_CLUSTERS,
    PCA_VARIANCE_THRESHOLD,
    apply_pca,
    _block_balance,
    _normalized_hourly_shape,
    _sign_convention,
    compute_series_features,
    run_clustering_and_selection,
    run_profiling_pipeline,
)

START = datetime(2012, 1, 2, 0, 0, 0)  # a Monday
N_WEEKS = 4
N_HOURS = N_WEEKS * 7 * 24


def _pattern_flat(hour, weekday, base):
    return base


def _pattern_daytime_peak(hour, weekday, base):
    return base * (1.6 if 8 <= hour < 18 else 0.5)


def _pattern_evening_peak(hour, weekday, base):
    return base * (1.8 if 18 <= hour < 22 else 0.5)


def _pattern_morning_peak(hour, weekday, base):
    return base * (1.7 if 6 <= hour < 10 else 0.5)


def _pattern_night_heavy(hour, weekday, base):
    return base * (1.6 if (hour < 5 or hour >= 22) else 0.6)


def _pattern_weekend_different(hour, weekday, base):
    if weekday < 5:
        return base * (1.5 if 8 <= hour < 18 else 0.5)
    return base * 0.9


def _pattern_variable(hour, weekday, base, rng):
    return max(0.1, base * (1.0 + rng.uniform(-0.6, 0.6)))


def _seed_series(db_session, series_name, base_kw, pattern_fn, noisy=False, seed=42):
    series = PublicLoadSeries(
        series_name=series_name,
        start_timestamp_local=START,
        frequency="hourly",
        value_count=N_HOURS,
        source_name="TEST FIXTURE",
        source_doi="10.5281/zenodo.4656140",
        source_url="https://zenodo.org/records/4656140",
        retrieved_at=datetime.now(),
        is_public_proxy=True,
    )
    db_session.add(series)
    db_session.commit()
    db_session.refresh(series)

    rng = np.random.default_rng(seed)
    rows = []
    for h in range(N_HOURS):
        ts = START + timedelta(hours=h)
        weekday = ts.weekday()
        if noisy:
            val = _pattern_variable(ts.hour, weekday, base_kw, rng)
        else:
            val = pattern_fn(ts.hour, weekday, base_kw)
        rows.append(
            PublicLoadObservation(
                series_id=series.id,
                timestamp_local=ts,
                hourly_average_kw=val,
                energy_kwh=val,
                interval_hours=1.0,
            )
        )
    db_session.bulk_save_objects(rows)
    db_session.commit()
    return series


@pytest.fixture
def seeded_series(db_session):
    estate = Estate(name="Test Estate", latitude=11.0168, longitude=76.9558)
    db_session.add(estate)
    db_session.commit()

    series = {}
    series["low_flat"] = _seed_series(db_session, "T_LOW_FLAT", 10.0, _pattern_flat)
    series["low_daytime"] = _seed_series(db_session, "T_LOW_DAYTIME", 12.0, _pattern_daytime_peak)
    series["high_flat"] = _seed_series(db_session, "T_HIGH_FLAT", 200.0, _pattern_flat)
    series["high_evening"] = _seed_series(db_session, "T_HIGH_EVENING", 220.0, _pattern_evening_peak)
    series["med_morning"] = _seed_series(db_session, "T_MED_MORNING", 80.0, _pattern_morning_peak)
    series["med_night"] = _seed_series(db_session, "T_MED_NIGHT", 75.0, _pattern_night_heavy)
    series["weekend_diff"] = _seed_series(db_session, "T_WEEKEND_DIFF", 100.0, _pattern_weekend_different)
    series["variable"] = _seed_series(db_session, "T_VARIABLE", 90.0, None, noisy=True)
    return series


def test_normalized_hourly_shape_sums_to_24():
    hours = list(range(24)) * 3
    values = [10.0 + (h % 24) for h in hours]
    df = pd.DataFrame({
        "timestamp_local": [START + timedelta(hours=h) for h in range(len(hours))],
        "energy_kwh": values,
    })
    shape = _normalized_hourly_shape(df)
    assert shape is not None
    assert len(shape) == 24
    assert math.isclose(sum(shape), 24.0, rel_tol=1e-6)


def test_normalized_hourly_shape_none_if_incomplete_hours():
    df = pd.DataFrame({
        "timestamp_local": [START + timedelta(hours=h) for h in range(10)],
        "energy_kwh": [1.0] * 10,
    })
    assert _normalized_hourly_shape(df) is None


def test_sign_convention_flips_negative_dominant_loading():
    components = np.array([[-0.9, 0.1, 0.2], [0.1, 0.2, -0.95]])
    flipped = _sign_convention(components)
    assert flipped[0, 0] > 0
    assert flipped[1, 2] > 0


def test_block_balance_gives_equal_total_variance_per_block():
    rng = np.random.default_rng(1)
    shape_block = rng.normal(size=(50, 8))
    scalar_block = rng.normal(size=(50, 2)) * 5
    combined = _block_balance(shape_block, scalar_block)
    shape_part = combined[:, :8]
    scalar_part = combined[:, 8:]
    shape_total_var = shape_part.var(axis=0, ddof=0).sum()
    scalar_total_var = scalar_part.var(axis=0, ddof=0).sum()
    assert math.isclose(shape_total_var, scalar_total_var, rel_tol=0.05)


def test_compute_features_basic_stats(db_session, seeded_series):
    f = compute_series_features(db_session, seeded_series["low_flat"])
    assert f is not None
    assert f.mean_demand_kw == pytest.approx(10.0, rel=1e-6)
    assert f.min_demand_kw == pytest.approx(10.0, rel=1e-6)
    assert f.max_demand_kw == pytest.approx(10.0, rel=1e-6)
    assert f.coefficient_of_variation == pytest.approx(0.0, abs=1e-9)
    assert f.peak_to_average_ratio == pytest.approx(1.0, rel=1e-6)


def test_compute_features_daytime_peak_shows_higher_day_night_ratio(db_session, seeded_series):
    f = compute_series_features(db_session, seeded_series["low_daytime"])
    assert f is not None
    assert f.day_night_ratio is not None
    assert f.day_night_ratio > 1.5


def test_compute_features_evening_peak_shows_high_tou_overlap(db_session, seeded_series):
    f = compute_series_features(db_session, seeded_series["high_evening"])
    flat = compute_series_features(db_session, seeded_series["high_flat"])
    assert f is not None and flat is not None
    assert f.tou_peak_overlap_pct > flat.tou_peak_overlap_pct


def test_compute_features_weekday_weekend_shapes_differ_for_weekend_diff_series(db_session, seeded_series):
    f = compute_series_features(db_session, seeded_series["weekend_diff"])
    assert f is not None
    weekday_range = max(f.weekday_shape) - min(f.weekday_shape)
    weekend_range = max(f.weekend_shape) - min(f.weekend_shape)
    assert weekday_range > weekend_range


def test_compute_features_shapes_sum_to_24(db_session, seeded_series):
    f = compute_series_features(db_session, seeded_series["med_morning"])
    assert math.isclose(sum(f.weekday_shape), 24.0, rel_tol=1e-6)
    assert math.isclose(sum(f.weekend_shape), 24.0, rel_tol=1e-6)


def test_apply_pca_meets_variance_threshold(db_session, seeded_series):
    features = [compute_series_features(db_session, s) for s in seeded_series.values()]
    matrix = np.array([f.weekday_shape for f in features])
    scores, n_components, variance = apply_pca(matrix)
    assert variance >= PCA_VARIANCE_THRESHOLD
    assert n_components >= 1
    assert scores.shape == (len(features), n_components)


def test_apply_pca_deterministic(db_session, seeded_series):
    features = [compute_series_features(db_session, s) for s in seeded_series.values()]
    matrix = np.array([f.weekday_shape for f in features])
    scores1, n1, var1 = apply_pca(matrix)
    scores2, n2, var2 = apply_pca(matrix)
    assert n1 == n2
    assert var1 == var2
    np.testing.assert_array_almost_equal(scores1, scores2)


def test_clustering_selects_exactly_six(db_session, seeded_series):
    features = [compute_series_features(db_session, s) for s in seeded_series.values()]
    result = run_clustering_and_selection(features)
    assert len(result.selected_indices) == N_CLUSTERS


def test_clustering_no_duplicate_series_selected(db_session, seeded_series):
    features = [compute_series_features(db_session, s) for s in seeded_series.values()]
    result = run_clustering_and_selection(features)
    names = [features[i].series_name for i in result.selected_indices]
    assert len(set(names)) == len(names)


def test_clustering_raises_if_fewer_than_six_series(db_session, seeded_series):
    features = [compute_series_features(db_session, s) for s in list(seeded_series.values())[:3]]
    with pytest.raises(LoadProfilingError):
        run_clustering_and_selection(features)


def test_clustering_deterministic_across_runs(db_session, seeded_series):
    features = [compute_series_features(db_session, s) for s in seeded_series.values()]
    result1 = run_clustering_and_selection(features)
    result2 = run_clustering_and_selection(features)
    names1 = sorted(features[i].series_name for i in result1.selected_indices)
    names2 = sorted(features[i].series_name for i in result2.selected_indices)
    assert names1 == names2


def test_full_pipeline_is_read_only_on_observations(db_session, seeded_series):
    before = db_session.query(PublicLoadObservation).count()
    run_profiling_pipeline(db_session, persist=True)
    after = db_session.query(PublicLoadObservation).count()
    assert before == after


def test_full_pipeline_persists_all_profiles_and_six_selected(db_session, seeded_series):
    summary = run_profiling_pipeline(db_session, persist=True)
    assert summary["total_series_profiled"] == 8
    assert summary["profile_rows_written"] == 8

    profiles = db_session.query(PublicLoadSeriesProfile).all()
    assert len(profiles) == 8
    selected = [p for p in profiles if p.is_selected]
    assert len(selected) == 6


def test_full_pipeline_validation_checks_all_pass(db_session, seeded_series):
    summary = run_profiling_pipeline(db_session, persist=True)
    checks = summary["validation_checks"]
    assert checks["exactly_six_selected"]["passed"] is True
    assert checks["no_duplicate_selection"]["passed"] is True
    assert checks["pca_variance_threshold_met"]["passed"] is True
    assert checks["observation_count_unchanged"]["passed"] is True


def test_full_pipeline_deterministic_end_to_end(db_session, seeded_series):
    summary1 = run_profiling_pipeline(db_session, persist=True)
    summary2 = run_profiling_pipeline(db_session, persist=True)
    names1 = sorted(p["series_name"] for p in summary1["selected_profiles"])
    names2 = sorted(p["series_name"] for p in summary2["selected_profiles"])
    assert names1 == names2


def test_full_pipeline_rerun_upserts_not_duplicates(db_session, seeded_series):
    run_profiling_pipeline(db_session, persist=True)
    run_profiling_pipeline(db_session, persist=True)
    profiles = db_session.query(PublicLoadSeriesProfile).all()
    assert len(profiles) == 8


def test_persisted_profile_json_fields_are_valid(db_session, seeded_series):
    run_profiling_pipeline(db_session, persist=True)
    profile = db_session.query(PublicLoadSeriesProfile).first()
    weekday_shape = json.loads(profile.weekday_shape_json)
    weekend_shape = json.loads(profile.weekend_shape_json)
    combined = json.loads(profile.combined_feature_vector_json)
    assert len(weekday_shape) == 24
    assert len(weekend_shape) == 24
    assert isinstance(combined, list) and len(combined) > 0


def test_selected_profiles_have_rationale_and_distance(db_session, seeded_series):
    run_profiling_pipeline(db_session, persist=True)
    selected = db_session.query(PublicLoadSeriesProfile).filter(PublicLoadSeriesProfile.is_selected == True).all()
    for p in selected:
        assert p.selection_rationale is not None
        assert p.distance_to_centroid is not None


def test_magnitude_spread_reported_across_selected(db_session, seeded_series):
    summary = run_profiling_pipeline(db_session, persist=True)
    detail = summary["validation_checks"]["magnitude_spread_reported"]["detail"]
    assert "min=" in detail and "max=" in detail


def test_flat_series_has_zero_or_near_zero_cv(db_session, seeded_series):
    f = compute_series_features(db_session, seeded_series["low_flat"])
    assert f.coefficient_of_variation < 1e-6
