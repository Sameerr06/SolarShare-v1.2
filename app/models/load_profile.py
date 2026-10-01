"""
Load-profile statistics and clustering results for the 321->6 tenant
profile selection methodology (v2, shape-aware).

One row per PublicLoadSeries. Computed by app/services/load_profiling.py,
which is strictly READ-ONLY against PublicLoadObservation -- profiling
must never alter the ingested 8,443,584 observation rows.

Storage split follows the approved design (§8/§9 of the methodology):
scalar statistics and shape vectors are persisted here for interpretation
and reproducibility auditing; the full pairwise distance matrix and
dendrogram are NOT persisted (fully regenerable from these stored features
plus the fixed, documented methodology).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import TimestampMixin
from app.models.types import UTCDateTime


class PublicLoadSeriesProfile(Base, TimestampMixin):
    __tablename__ = "public_load_series_profiles"
    __table_args__ = (
        UniqueConstraint("series_id", "methodology_version", name="uq_profile_series_methodology"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("public_load_series.id"), nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v2_shape_aware")

    # --- Raw/non-normalized magnitude statistics (interpretation, validation) ---
    mean_demand_kw: Mapped[float] = mapped_column(Float, nullable=False)
    median_demand_kw: Mapped[float] = mapped_column(Float, nullable=False)
    min_demand_kw: Mapped[float] = mapped_column(Float, nullable=False)
    max_demand_kw: Mapped[float] = mapped_column(Float, nullable=False)
    std_demand_kw: Mapped[float] = mapped_column(Float, nullable=False)
    observation_count: Mapped[int] = mapped_column(Integer, nullable=False)

    # --- Scalar shape features (genuine clustering inputs) ---
    coefficient_of_variation: Mapped[float] = mapped_column(Float, nullable=False)
    peak_to_average_ratio: Mapped[float] = mapped_column(Float, nullable=False)

    # --- Reported-only metrics (derived from shape, NOT clustering inputs --
    #     see methodology §2: would double-count the shape vector's signal) ---
    day_night_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tou_peak_overlap_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    weekday_weekend_ratio: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # --- Temporal shape vectors (24 values each, JSON-encoded), normalized
    #     by each vector's own mean (see methodology §1) ---
    weekday_shape_json: Mapped[str] = mapped_column(Text, nullable=False)
    weekend_shape_json: Mapped[str] = mapped_column(Text, nullable=False)

    # --- PCA scores (JSON-encoded list), retained components only ---
    weekday_pca_scores_json: Mapped[str] = mapped_column(Text, nullable=False)
    weekend_pca_scores_json: Mapped[str] = mapped_column(Text, nullable=False)

    # --- Combined, block-balanced feature vector used for clustering ---
    combined_feature_vector_json: Mapped[str] = mapped_column(Text, nullable=False)

    # --- Clustering results ---
    cluster_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_selected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    distance_to_centroid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    selection_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    computed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<PublicLoadSeriesProfile series_id={self.series_id} cluster={self.cluster_id} "
            f"selected={self.is_selected}>"
        )
