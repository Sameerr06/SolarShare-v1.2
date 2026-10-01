"""
Weather/solar-data ingestion entities.

`WeatherObservation` stores validated, per-hour NASA POWER records with full
provenance (per the locked specification §14). `NasaPowerCache` stores raw
API responses keyed by request parameters so identical requests are never
silently re-fetched or mixed up across locations/date ranges (§15).
`SolarGenerationEstimate` stores the *derived* estimated electrical
generation figure — kept as a clearly separate table/concept from the raw
NASA observation, per the "NASA solar-radiation observation vs. SolarShare
estimated electrical generation" distinction (§13/§20 of the specification).
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import TimestampMixin
from app.models.types import UTCDateTime


class WeatherObservation(Base, TimestampMixin):
    """
    One validated hourly NASA POWER record for an estate.

    `timestamp` is always stored in UTC (per the locked specification §5 —
    UTC is the canonical internal representation; localization to
    Asia/Kolkata happens only at presentation time, never in storage).
    """

    __tablename__ = "weather_observations"
    __table_args__ = (
        UniqueConstraint("estate_id", "timestamp", name="uq_weather_obs_estate_timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    estate_id: Mapped[int] = mapped_column(ForeignKey("estates.id"), nullable=False)

    timestamp: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)

    # ALLSKY_SFC_SW_DWN — GHI, W/m² average for the hour (RE community,
    # Hourly Point API). See app/integrations/nasa_power.py module docstring
    # for the full unit-verification conclusion.
    allsky_sfc_sw_dwn: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    t2m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # temperature, °C
    rh2m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # relative humidity, %
    ws10m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # wind speed, m/s

    # --- Provenance (locked specification §14) ---
    source_name: Mapped[str] = mapped_column(String(64), nullable=False, default="NASA POWER")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, default="NASA_POWER")
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    community: Mapped[str] = mapped_column(String(16), nullable=False, default="RE")
    parameters_requested: Mapped[str] = mapped_column(String(255), nullable=False)
    time_standard: Mapped[str] = mapped_column(String(16), nullable=False, default="UTC")
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    units: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="ALLSKY_SFC_SW_DWN=W/m^2 (hourly average GHI); T2M=degC; RH2M=%; WS10M=m/s",
    )
    processing_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    data_status: Mapped[str] = mapped_column(String(16), nullable=False, default="LIVE")  # LIVE | CACHED | DEMO

    def __repr__(self) -> str:
        return f"<WeatherObservation estate_id={self.estate_id} ts={self.timestamp} ghi={self.allsky_sfc_sw_dwn}>"


class NasaPowerCache(Base, TimestampMixin):
    """
    Raw NASA POWER API response cache.

    `cache_key` is a deterministic hash of (latitude, longitude, parameters,
    start_date, end_date, community, time_standard) — see
    app/integrations/nasa_power.py `build_cache_key()`. This guarantees a
    cache lookup can never accidentally return data for a different
    location/date range/parameter set (§15).
    """

    __tablename__ = "nasa_power_cache"

    id: Mapped[int] = mapped_column(primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    parameters: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[str] = mapped_column(String(8), nullable=False)  # YYYYMMDD
    end_date: Mapped[str] = mapped_column(String(8), nullable=False)  # YYYYMMDD
    community: Mapped[str] = mapped_column(String(16), nullable=False)
    time_standard: Mapped[str] = mapped_column(String(16), nullable=False)

    raw_response_json: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)

    def __repr__(self) -> str:
        return f"<NasaPowerCache key={self.cache_key} range={self.start_date}-{self.end_date}>"


class SolarGenerationEstimate(Base, TimestampMixin):
    """
    Derived, estimated electrical generation — explicitly NOT a raw NASA
    observation. Computed from a WeatherObservation + the active PVConfig
    at the time of estimation (see app/services/solar_generation.py).
    """

    __tablename__ = "solar_generation_estimates"
    __table_args__ = (
        UniqueConstraint("estate_id", "timestamp", name="uq_solar_gen_estate_timestamp"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    estate_id: Mapped[int] = mapped_column(ForeignKey("estates.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, index=True)

    estimated_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    pv_config_id: Mapped[int] = mapped_column(ForeignKey("pv_configs.id"), nullable=False)
    weather_observation_id: Mapped[int] = mapped_column(ForeignKey("weather_observations.id"), nullable=False)

    notes: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default=(
            "Simplified prototype estimation model, not a full physical PV simulation. "
            "See app/services/solar_generation.py for the documented formula and unit conversion."
        ),
    )

    def __repr__(self) -> str:
        return f"<SolarGenerationEstimate estate_id={self.estate_id} ts={self.timestamp} kwh={self.estimated_kwh}>"
