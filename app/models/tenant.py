"""
Tenant entity.

`profile_type` holds one of the six locked SolarShare demo profiles.
`source_client_series_id` will hold the deterministically-selected Zenodo
client ID once the Phase 2 data-profiling/selection step runs — nullable
for now since that selection hasn't happened yet in Phase 1.
"""

from typing import Optional, TYPE_CHECKING

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import TenantProfileType
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.estate import Estate
    from app.models.user import User


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    estate_id: Mapped[int] = mapped_column(ForeignKey("estates.id"), nullable=False)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    profile_type: Mapped[TenantProfileType] = mapped_column(
        SAEnum(TenantProfileType, native_enum=False, length=64), nullable=False
    )

    # Populated in a later phase by the deterministic client-selection /
    # data-profiling step described in the locked specification (§8).
    source_client_series_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    estate: Mapped["Estate"] = relationship(back_populates="tenants")
    users: Mapped[list["User"]] = relationship(back_populates="tenant")

    def __repr__(self) -> str:
        return f"<Tenant id={self.id} name={self.name!r} profile={self.profile_type.value}>"
