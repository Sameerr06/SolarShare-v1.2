"""
Public electricity dataset ingestion entities.

Two tables, deliberately kept separate to preserve the distinction between
SOURCE data and DERIVED data (per the locked specification and this
session's unit-interpretation lock):

- `PublicLoadSeries`: one row per raw series in the source .tsf file
  (e.g. "T1", "T2", ...), carrying full source provenance. This is NOT yet
  mapped to any SolarShare Tenant — that mapping is a later, separate step
  (the deterministic client-selection process), intentionally not done here.
- `PublicLoadObservation`: one row per (series, timestamp), carrying BOTH
  the untouched source value (`hourly_average_kw`) and the derived,
  converted value (`energy_kwh`) side by side — so the source figure is
  always independently inspectable, never overwritten by the conversion.

Per the locked unit interpretation:
    SOURCE:  "Hourly average electricity demand in kW."
    DERIVED: "Hourly energy consumption in kWh."
    energy_kwh = hourly_average_kw * interval_hours   (interval_hours = 1.0
                 for this dataset — see app/integrations/electricity_dataset.py
                 for the full Energy = Power x Time documentation).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import TimestampMixin


class PublicLoadSeries(Base, TimestampMixin):
    """
    One raw series from the public electricity dataset (.tsf file),
    identified by its native series name (e.g. "T1"). NOT yet linked to any
    Tenant — tenant mapping happens in the (separate, not-yet-implemented)
    deterministic client-selection step.
    """

    __tablename__ = "public_load_series"

    id: Mapped[int] = mapped_column(primary_key=True)
    series_name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    start_timestamp_local: Mapped[datetime] = mapped_column(nullable=False)
    frequency: Mapped[str] = mapped_column(String(32), nullable=False)
    value_count: Mapped[int] = mapped_column(nullable=False)

    # --- Source provenance ---
    source_name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_doi: Mapped[str] = mapped_column(String(128), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    source_unit_description: Mapped[str] = mapped_column(
        String(255), nullable=False, default="Hourly average electricity demand in kW."
    )
    retrieved_at: Mapped[datetime] = mapped_column(nullable=False)
    processing_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")

    is_public_proxy: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Always True: labels this as public proxy data, never actual Coimbatore MSME data.",
    )
    provenance_label: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default=(
            "Public electricity-consumption dataset used as a tenant-load proxy. "
            "Not actual Coimbatore MSME smart-meter data."
        ),
    )

    def __repr__(self) -> str:
        return f"<PublicLoadSeries name={self.series_name!r} n={self.value_count}>"


class PublicLoadObservation(Base, TimestampMixin):
    """
    One (series, timestamp) reading: source value and derived value stored
    side by side, never conflated.
    """

    __tablename__ = "public_load_observations"
    __table_args__ = (
        UniqueConstraint("series_id", "timestamp_local", name="uq_public_load_obs_series_timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    series_id: Mapped[int] = mapped_column(ForeignKey("public_load_series.id"), nullable=False)

    # Source timestamps are in the source's own local clock time
    # ("Portuguese hour" per the source documentation), deliberately NOT
    # stored using the UTCDateTime type used for NASA POWER data — mixing
    # those would violate the "do not mix NASA Local Solar Time with
    # tenant electricity timestamps" requirement from the locked
    # specification. Converting this to a precise UTC value (correctly
    # handling the source's documented DST irregularities) is out of scope
    # for this ingestion milestone and is called out as a known limitation.
    timestamp_local: Mapped[datetime] = mapped_column(nullable=False, index=True)

    # --- SOURCE value (untouched) ---
    hourly_average_kw: Mapped[Optional[float]] = mapped_column(
        Float, nullable=True, doc="Raw source value: hourly average electricity demand in kW. None = missing/'?'."
    )

    # --- DERIVED value ---
    energy_kwh: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        doc="Derived: hourly energy consumption in kWh (Energy = Power x Time, "
        "interval_hours = 1.0). None when the source value is missing.",
    )
    interval_hours: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    def __repr__(self) -> str:
        return (
            f"<PublicLoadObservation series_id={self.series_id} ts={self.timestamp_local} "
            f"kw={self.hourly_average_kw} kwh={self.energy_kwh}>"
        )
