"""
PVConfig and BatteryConfig entities.

Both are explicitly PROTOTYPE ASSUMPTIONS per the locked specification —
never actual installed-equipment specifications — and both are designed to
be editable/versioned via `effective_from` + `is_active`, never hardcoded
into PV-estimation or battery-simulation logic (those arrive in Phase 2+).
"""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.estate import Estate


class PVConfig(Base, TimestampMixin):
    """
    Prototype PV system configuration for an estate.

    GENERATION-MODEL NOTE (locked as of the Phase 2 solar-generation-model
    review — see app/services/solar_generation.py for the full rationale):
    `capacity_kw` is the STC-rated electrical output of the installed
    system and IS used directly in the generation calculation, along with
    `performance_ratio`. `efficiency` is retained here as DESCRIPTIVE
    CONFIGURATION METADATA ONLY (documenting the panel technology /
    approximate footprint implied by that capacity) — it is deliberately
    NOT read by the generation formula, to avoid double-counting a loss
    that `capacity_kw` (as an STC rating) already reflects.
    """

    __tablename__ = "pv_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    estate_id: Mapped[int] = mapped_column(ForeignKey("estates.id"), nullable=False)

    # STC-rated electrical output of the installed PV system (kW). This is
    # the figure actually used in generation calculations
    # (app/services/solar_generation.py) — see class docstring above.
    capacity_kw: Mapped[float] = mapped_column(Float, nullable=False)

    # Descriptive/configuration metadata only (e.g. panel technology
    # efficiency, ~20%). NOT used as a multiplier in the generation
    # formula — see class docstring above for why.
    efficiency: Mapped[float] = mapped_column(Float, nullable=False)  # e.g. 0.20, metadata only

    # Real-world derating applied on top of the STC-rated capacity_kw
    # (temperature, wiring, inverter, soiling, mismatch losses combined).
    # Used directly in the generation calculation.
    performance_ratio: Mapped[float] = mapped_column(Float, nullable=False)  # e.g. 0.80

    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="Prototype PV configuration assumption — not an actual installed-equipment specification.",
    )

    estate: Mapped["Estate"] = relationship(back_populates="pv_configs")

    def __repr__(self) -> str:
        return f"<PVConfig id={self.id} capacity_kw={self.capacity_kw} active={self.is_active}>"


class BatteryConfig(Base, TimestampMixin):
    __tablename__ = "battery_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    estate_id: Mapped[int] = mapped_column(ForeignKey("estates.id"), nullable=False)

    capacity_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    initial_soc_pct: Mapped[float] = mapped_column(Float, nullable=False)
    min_soc_pct: Mapped[float] = mapped_column(Float, nullable=False)
    max_soc_pct: Mapped[float] = mapped_column(Float, nullable=False)
    max_charge_kw: Mapped[float] = mapped_column(Float, nullable=False)
    max_discharge_kw: Mapped[float] = mapped_column(Float, nullable=False)
    round_trip_efficiency: Mapped[float] = mapped_column(Float, nullable=False)  # e.g. 0.90

    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="Prototype battery configuration assumption — not an actual hardware specification.",
    )

    estate: Mapped["Estate"] = relationship(back_populates="battery_configs")

    def __repr__(self) -> str:
        return f"<BatteryConfig id={self.id} capacity_kwh={self.capacity_kwh} active={self.is_active}>"
