"""
Estate entity.

Per the locked specification: the estate's location (Coimbatore,
lat 11.0168 / lon 76.9558) is stored here and read by later phases'
NASA POWER ingestion — never hardcoded into ingestion code.
"""

from typing import List, TYPE_CHECKING

from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.config import PVConfig, BatteryConfig


class Estate(Base, TimestampMixin):
    __tablename__ = "estates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Kolkata")

    tenants: Mapped[List["Tenant"]] = relationship(back_populates="estate")
    pv_configs: Mapped[List["PVConfig"]] = relationship(back_populates="estate")
    battery_configs: Mapped[List["BatteryConfig"]] = relationship(back_populates="estate")

    def __repr__(self) -> str:
        return f"<Estate id={self.id} name={self.name!r} lat={self.latitude} lon={self.longitude}>"
