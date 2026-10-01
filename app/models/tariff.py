"""
Tariff, TariffPeriod, and SolarTariffConfig entities.

Per the locked specification, the Tamil Nadu ToU tariff must be stored as
configurable data (never hardcoded into billing functions), labeled clearly
as a prototype configuration tied to a specific source, and structured so
future TNERC revisions can be added as new rows without a code change.

Phase 1 defines the schema only. Seeding the actual FY 2025-26 rates and
building the billing engine that consumes them are later-phase work.
"""

from datetime import datetime, time
from typing import List

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Time
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import TariffPeriodName
from app.models.mixins import TimestampMixin


class Tariff(Base, TimestampMixin):
    __tablename__ = "tariffs"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), nullable=False, default="INDUSTRIAL")
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(1000), nullable=False)
    label: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="Tamil Nadu FY 2025-26 prototype tariff configuration",
    )

    periods: Mapped[List["TariffPeriod"]] = relationship(back_populates="tariff")

    def __repr__(self) -> str:
        return f"<Tariff id={self.id} name={self.name!r}>"


class TariffPeriod(Base, TimestampMixin):
    __tablename__ = "tariff_periods"

    id: Mapped[int] = mapped_column(primary_key=True)
    tariff_id: Mapped[int] = mapped_column(ForeignKey("tariffs.id"), nullable=False)

    period_name: Mapped[TariffPeriodName] = mapped_column(
        SAEnum(TariffPeriodName, native_enum=False, length=32), nullable=False
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    base_energy_charge_inr_per_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    electricity_tax_pct: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    effective_rate_inr_per_kwh: Mapped[float] = mapped_column(Float, nullable=False)

    tariff: Mapped["Tariff"] = relationship(back_populates="periods")

    def __repr__(self) -> str:
        return (
            f"<TariffPeriod id={self.id} period={self.period_name.value} "
            f"{self.start_time}-{self.end_time} rate={self.effective_rate_inr_per_kwh}>"
        )


class SolarTariffConfig(Base, TimestampMixin):
    """
    SolarShare's own internal solar tariff — a prototype business
    assumption, explicitly distinct from the Tamil Nadu grid ToU tariff.
    """

    __tablename__ = "solar_tariff_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    estate_id: Mapped[int] = mapped_column(ForeignKey("estates.id"), nullable=False)

    rate_inr_per_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    notes: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        default="SolarShare internal prototype business assumption — not an official electricity tariff.",
    )

    def __repr__(self) -> str:
        return f"<SolarTariffConfig id={self.id} rate={self.rate_inr_per_kwh}>"
