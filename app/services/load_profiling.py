"""
321 -> 6 tenant load-profile selection pipeline (methodology v2, shape-aware).

Implements the approved methodology in full:
    profile all 321 series
    -> weekday/weekend 24h median shape, normalized by own mean
    -> PCA on each shape matrix (>=90% variance retained)
    -> combine PCA scores + CV + PAR (day/night ratio and ToU-overlap are
       DERIVED FROM shape and are reported-only, never added as extra
       clustering dimensions -- they would double-count the shape signal)
    -> standardize, then block-balance (shape block vs scalar block
       contribute equal total variance)
    -> deterministic Ward hierarchical clustering, k=6
    -> select the real series nearest each cluster centroid
    -> validate

STRICTLY READ-ONLY against PublicLoadObservation. Never inserts, updates,
or deletes an observation row. Persists results only to
PublicLoadSeriesProfile.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import fcluster, linkage
from sklearn.decomposition import PCA
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.load_profile import PublicLoadSeriesProfile
from app.models.public_load import PublicLoadObservation, PublicLoadSeries

logger = logging.getLogger(__name__)

METHODOLOGY_VERSION = "v2_shape_aware"

# Locked Tamil Nadu ToU periods -- used only to compute the REPORTED
# tou_peak_overlap_pct metric, never as a clustering input.
MORNING_PEAK_HOURS = range(6, 10)   # 06:00-10:00
EVENING_PEAK_HOURS = range(18, 22)  # 18:00-22:00
DAYTIME_HOURS = range(6, 18)        # 06:00-18:00, used for day/night ratio

PCA_VARIANCE_THRESHOLD = 0.90
N_CLUSTERS = 6


class LoadProfilingError(Exception):
    pass


@dataclass
class SeriesRawFeatures:
    series_id: int
    series_name: str
    mean_demand_kw: float
    median_demand_kw: float
    min_demand_kw: float
    max_demand_kw: float
    std_demand_kw: float
    observation_count: int
    coefficient_of_variation: float
    peak_to_average_ratio: float
    day_night_ratio: Optional[float]
    tou_peak_overlap_pct: Optional[float]
    weekday_weekend_ratio: Optional[float]
    weekday_shape: List[float]
    weekend_shape: List[float]


def _load_series_dataframe(db: Session, series_id: int) -> pd.DataFrame:
    """
    Stream one series' observations into a DataFrame. One series at a time
    (~26,304 rows for the real dataset) -- never all 321 series at once.
    """
    stmt = (
        select(PublicLoadObservation.timestamp_local, PublicLoadObservation.energy_kwh)
        .where(PublicLoadObservation.series_id == series_id)
        .order_by(PublicLoadObservation.timestamp_local)
    )
    rows = db.execute(stmt).all()
    return pd.DataFrame(rows, columns=["timestamp_local", "energy_kwh"])


def _normalized_hourly_shape(df: pd.DataFrame) -> Optional[List[float]]:
    """
    Median value at each hour-of-day (0-23), normalized by the resulting
    24-vector's own mean. Returns None if there isn't at least one valid
    reading for every one of the 24 hours.
    """
    if df.empty:
        return None
    hourly_median = df.groupby(df["timestamp_local"].dt.hour)["energy_kwh"].median()
    if len(hourly_median) < 24 or hourly_median.isna().any():
        return None
    shape = hourly_median.reindex(range(24)).to_numpy(dtype=float)
    shape_mean = shape.mean()
    if shape_mean == 0:
        return None
    return (shape / shape_mean).tolist()


def compute_series_features(db: Session, series_row: PublicLoadSeries) -> Optional[SeriesRawFeatures]:
    """Compute all raw/scalar/shape features for ONE series."""
    df = _load_series_dataframe(db, series_row.id)
    df = df.dropna(subset=["energy_kwh"])

    if df.empty:
        logger.warning("Series %s has no valid observations; skipped.", series_row.series_name)
        return None

    values = df["energy_kwh"].to_numpy(dtype=float)
    mean_demand = float(values.mean())
    std_demand = float(values.std(ddof=0))

    if mean_demand == 0:
        logger.warning("Series %s has zero mean demand; CV/PAR undefined, skipped.", series_row.series_name)
        return None
    cv = std_demand / mean_demand
    par = float(values.max()) / mean_demand

    hours = df["timestamp_local"].dt.hour
    is_weekday = df["timestamp_local"].dt.weekday < 5

    daytime_mask = hours.isin(list(DAYTIME_HOURS))
    daytime_mean = df.loc[daytime_mask, "energy_kwh"].mean()
    nighttime_mean = df.loc[~daytime_mask, "energy_kwh"].mean()
    day_night_ratio = (
        float(daytime_mean / nighttime_mean)
        if pd.notna(daytime_mean) and pd.notna(nighttime_mean) and nighttime_mean != 0
        else None
    )

    tou_peak_mask = hours.isin(list(MORNING_PEAK_HOURS)) | hours.isin(list(EVENING_PEAK_HOURS))
    total_energy = df["energy_kwh"].sum()
    tou_peak_overlap_pct = (
        float(100.0 * df.loc[tou_peak_mask, "energy_kwh"].sum() / total_energy)
        if total_energy != 0
        else None
    )

    weekday_mean = df.loc[is_weekday, "energy_kwh"].mean()
    weekend_mean = df.loc[~is_weekday, "energy_kwh"].mean()
    weekday_weekend_ratio = (
        float(weekday_mean / weekend_mean)
        if pd.notna(weekday_mean) and pd.notna(weekend_mean) and weekend_mean != 0
        else None
    )

    weekday_shape = _normalized_hourly_shape(df[is_weekday])
    weekend_shape = _normalized_hourly_shape(df[~is_weekday])
    if weekday_shape is None or weekend_shape is None:
        logger.warning(
            "Series %s lacks full 24-hour coverage on weekday or weekend side; skipped.",
            series_row.series_name,
        )
        return None

    return SeriesRawFeatures(
        series_id=series_row.id,
        series_name=series_row.series_name,
        mean_demand_kw=mean_demand,
        median_demand_kw=float(np.median(values)),
        min_demand_kw=float(values.min()),
        max_demand_kw=float(values.max()),
        std_demand_kw=std_demand,
        observation_count=int(len(values)),
        coefficient_of_variation=cv,
        peak_to_average_ratio=par,
        day_night_ratio=day_night_ratio,
        tou_peak_overlap_pct=tou_peak_overlap_pct,
        weekday_weekend_ratio=weekday_weekend_ratio,
        weekday_shape=weekday_shape,
        weekend_shape=weekend_shape,
    )


def compute_all_profiles(db: Session) -> Tuple[List[SeriesRawFeatures], List[str]]:
    """Compute features for every series, in fixed order (sorted by series_name)."""
    series_rows = db.query(PublicLoadSeries).order_by(PublicLoadSeries.series_name).all()
    features: List[SeriesRawFeatures] = []
    skipped: List[str] = []
    for series_row in series_rows:
        f = compute_series_features(db, series_row)
        if f is None:
            skipped.append(series_row.series_name)
        else:
            features.append(f)
    return features, skipped


def _sign_convention(components: np.ndarray) -> np.ndarray:
    """Deterministic PCA sign convention: largest-magnitude loading positive."""
    flipped = components.copy()
    for i in range(components.shape[0]):
        row = components[i]
        max_idx = np.argmax(np.abs(row))
        if row[max_idx] < 0:
            flipped[i] = -row
    return flipped


def apply_pca(shape_matrix: np.ndarray, variance_threshold: float = PCA_VARIANCE_THRESHOLD):
    """
    Deterministic PCA: retains the minimum number of components reaching
    `variance_threshold` cumulative explained variance, applies the fixed
    sign convention.
    """
    pca_full = PCA(n_components=None, svd_solver="full", random_state=0)
    pca_full.fit(shape_matrix)
    cumulative = np.cumsum(pca_full.explained_variance_ratio_)
    n_components = int(np.searchsorted(cumulative, variance_threshold) + 1)
    n_components = min(n_components, shape_matrix.shape[1])

    pca = PCA(n_components=n_components, svd_solver="full", random_state=0)
    pca.fit(shape_matrix)
    components_signed = _sign_convention(pca.components_)

    centered = shape_matrix - pca.mean_
    scores_signed = centered @ components_signed.T

    variance_explained = float(np.sum(pca.explained_variance_ratio_))
    return scores_signed, n_components, variance_explained


def _block_balance(shape_block: np.ndarray, scalar_block: np.ndarray) -> np.ndarray:
    """
    Z-score each column, then rescale each BLOCK so its total variance
    equals 1 (divide by sqrt(number of columns in that block)) -- so the
    shape block (more dimensions) can't dominate purely by dimension count.
    """
    def _zscore(block: np.ndarray) -> np.ndarray:
        mean = block.mean(axis=0)
        std = block.std(axis=0, ddof=0)
        std_safe = np.where(std == 0, 1.0, std)
        return (block - mean) / std_safe

    shape_z = _zscore(shape_block)
    scalar_z = _zscore(scalar_block)
    shape_balanced = shape_z / np.sqrt(shape_z.shape[1])
    scalar_balanced = scalar_z / np.sqrt(scalar_z.shape[1])
    return np.concatenate([shape_balanced, scalar_balanced], axis=1)


@dataclass
class ProfilingResult:
    features: List[SeriesRawFeatures]
    skipped_series: List[str]
    weekday_pca_n_components: int
    weekday_pca_variance_explained: float
    weekend_pca_n_components: int
    weekend_pca_variance_explained: float
    combined_features: np.ndarray
    cluster_ids: np.ndarray
    selected_indices: List[int]
    distances_to_centroid: List[float]
    weekday_pca_scores: np.ndarray
    weekend_pca_scores: np.ndarray


def run_clustering_and_selection(features: List[SeriesRawFeatures]) -> ProfilingResult:
    if len(features) < N_CLUSTERS:
        raise LoadProfilingError(
            f"Need at least {N_CLUSTERS} valid series to select {N_CLUSTERS} clusters, got {len(features)}"
        )

    weekday_matrix = np.array([f.weekday_shape for f in features])
    weekend_matrix = np.array([f.weekend_shape for f in features])

    weekday_scores, weekday_n, weekday_var = apply_pca(weekday_matrix)
    weekend_scores, weekend_n, weekend_var = apply_pca(weekend_matrix)

    shape_block = np.concatenate([weekday_scores, weekend_scores], axis=1)
    scalar_block = np.array([[f.coefficient_of_variation, f.peak_to_average_ratio] for f in features])

    combined = _block_balance(shape_block, scalar_block)

    Z = linkage(combined, method="ward")
    cluster_ids = fcluster(Z, t=N_CLUSTERS, criterion="maxclust")

    selected_indices: List[int] = []
    distances: List[float] = []
    for cluster_num in sorted(set(cluster_ids)):
        member_indices = [i for i, c in enumerate(cluster_ids) if c == cluster_num]
        member_vectors = combined[member_indices]
        centroid = member_vectors.mean(axis=0)
        dists = np.linalg.norm(member_vectors - centroid, axis=1)

        min_dist = dists.min()
        tied = [member_indices[i] for i, d in enumerate(dists) if d == min_dist]
        tied.sort(key=lambda idx: features[idx].series_name)
        chosen = tied[0]

        selected_indices.append(chosen)
        distances.append(float(min_dist))

    return ProfilingResult(
        features=features,
        skipped_series=[],
        weekday_pca_n_components=weekday_n,
        weekday_pca_variance_explained=weekday_var,
        weekend_pca_n_components=weekend_n,
        weekend_pca_variance_explained=weekend_var,
        combined_features=combined,
        cluster_ids=cluster_ids,
        selected_indices=selected_indices,
        distances_to_centroid=distances,
        weekday_pca_scores=weekday_scores,
        weekend_pca_scores=weekend_scores,
    )


def validate_result(db: Session, result: ProfilingResult, expected_observation_count: Optional[int] = None) -> Dict:
    checks: Dict[str, Tuple[bool, str]] = {}

    checks["exactly_six_selected"] = (
        len(result.selected_indices) == N_CLUSTERS,
        f"{len(result.selected_indices)} selected",
    )

    selected_names = [result.features[i].series_name for i in result.selected_indices]
    checks["no_duplicate_selection"] = (
        len(set(selected_names)) == len(selected_names),
        f"{len(set(selected_names))} unique of {len(selected_names)}",
    )

    checks["pca_variance_threshold_met"] = (
        result.weekday_pca_variance_explained >= PCA_VARIANCE_THRESHOLD
        and result.weekend_pca_variance_explained >= PCA_VARIANCE_THRESHOLD,
        f"weekday={result.weekday_pca_variance_explained:.3f} weekend={result.weekend_pca_variance_explained:.3f}",
    )

    selected_vectors = result.combined_features[result.selected_indices]
    if len(selected_vectors) >= 2:
        pairwise_min = min(
            np.linalg.norm(selected_vectors[i] - selected_vectors[j])
            for i in range(len(selected_vectors))
            for j in range(i + 1, len(selected_vectors))
        )
    else:
        pairwise_min = float("nan")
    checks["min_pairwise_distance_reported"] = (True, f"{pairwise_min:.4f}")

    magnitudes = [result.features[i].mean_demand_kw for i in result.selected_indices]
    checks["magnitude_spread_reported"] = (True, f"min={min(magnitudes):.2f} max={max(magnitudes):.2f} kW")

    if expected_observation_count is not None:
        actual_count = db.query(PublicLoadObservation).count()
        checks["observation_count_unchanged"] = (
            actual_count == expected_observation_count,
            f"expected={expected_observation_count} actual={actual_count}",
        )

    return checks


def _persist_profiles(db: Session, result: ProfilingResult, methodology_version: str = METHODOLOGY_VERSION) -> int:
    computed_at = datetime.now(timezone.utc)
    written = 0
    selected_set = set(result.selected_indices)

    for i, f in enumerate(result.features):
        existing = (
            db.query(PublicLoadSeriesProfile)
            .filter(
                PublicLoadSeriesProfile.series_id == f.series_id,
                PublicLoadSeriesProfile.methodology_version == methodology_version,
            )
            .first()
        )
        target = existing or PublicLoadSeriesProfile(series_id=f.series_id, methodology_version=methodology_version)

        target.mean_demand_kw = f.mean_demand_kw
        target.median_demand_kw = f.median_demand_kw
        target.min_demand_kw = f.min_demand_kw
        target.max_demand_kw = f.max_demand_kw
        target.std_demand_kw = f.std_demand_kw
        target.observation_count = f.observation_count
        target.coefficient_of_variation = f.coefficient_of_variation
        target.peak_to_average_ratio = f.peak_to_average_ratio
        target.day_night_ratio = f.day_night_ratio
        target.tou_peak_overlap_pct = f.tou_peak_overlap_pct
        target.weekday_weekend_ratio = f.weekday_weekend_ratio
        target.weekday_shape_json = json.dumps(f.weekday_shape)
        target.weekend_shape_json = json.dumps(f.weekend_shape)
        target.weekday_pca_scores_json = json.dumps(result.weekday_pca_scores[i].tolist())
        target.weekend_pca_scores_json = json.dumps(result.weekend_pca_scores[i].tolist())
        target.combined_feature_vector_json = json.dumps(result.combined_features[i].tolist())
        target.cluster_id = int(result.cluster_ids[i])
        target.is_selected = i in selected_set
        if i in selected_set:
            idx_in_selected = result.selected_indices.index(i)
            target.distance_to_centroid = result.distances_to_centroid[idx_in_selected]
            target.selection_rationale = (
                f"Nearest to centroid of cluster {result.cluster_ids[i]} "
                f"(distance={result.distances_to_centroid[idx_in_selected]:.4f}), "
                f"methodology {methodology_version}."
            )
        target.computed_at = computed_at

        if existing is None:
            db.add(target)
        written += 1

    db.commit()
    return written


def run_profiling_pipeline(db: Session, persist: bool = True) -> Dict:
    """
    Full orchestration: profile all series, cluster, select, validate, and
    (optionally) persist. Read-only against PublicLoadObservation.
    """
    observation_count_before = db.query(PublicLoadObservation).count()

    features, skipped = compute_all_profiles(db)
    result = run_clustering_and_selection(features)
    result.skipped_series = skipped

    checks = validate_result(db, result, expected_observation_count=observation_count_before)
    written = _persist_profiles(db, result) if persist else 0

    selected_report = [
        {
            "series_name": result.features[i].series_name,
            "cluster_id": int(result.cluster_ids[i]),
            "mean_demand_kw": result.features[i].mean_demand_kw,
            "cv": result.features[i].coefficient_of_variation,
            "par": result.features[i].peak_to_average_ratio,
            "day_night_ratio": result.features[i].day_night_ratio,
            "tou_peak_overlap_pct": result.features[i].tou_peak_overlap_pct,
            "distance_to_centroid": dist,
        }
        for i, dist in zip(result.selected_indices, result.distances_to_centroid)
    ]

    return {
        "methodology_version": METHODOLOGY_VERSION,
        "total_series_profiled": len(result.features),
        "series_skipped": skipped,
        "weekday_pca_n_components": result.weekday_pca_n_components,
        "weekday_pca_variance_explained": result.weekday_pca_variance_explained,
        "weekend_pca_n_components": result.weekend_pca_n_components,
        "weekend_pca_variance_explained": result.weekend_pca_variance_explained,
        "selected_profiles": selected_report,
        "validation_checks": {k: {"passed": v[0], "detail": v[1]} for k, v in checks.items()},
        "profile_rows_written": written,
        "observation_count_before": observation_count_before,
    }
