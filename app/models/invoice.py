"""Invoice and line-item ORM models for billing."""

from datetime import datetime
from typing import List

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin


class Invoice(Base, TimestampMixin):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    billing_period: Mapped[str] = mapped_column(String(7), nullable=False, index=True)  # YYYY-MM
    issue_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="ISSUED", nullable=False)

    total_consumption_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    solar_consumed_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    grid_consumed_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    solar_cost_inr: Mapped[float] = mapped_column(Float, nullable=False)
    grid_cost_inr: Mapped[float] = mapped_column(Float, nullable=False)
    total_bill_inr: Mapped[float] = mapped_column(Float, nullable=False)
    savings_inr: Mapped[float] = mapped_column(Float, nullable=False)

    line_items: Mapped[List["InvoiceLineItem"]] = relationship(
        "InvoiceLineItem",
        back_populates="invoice",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
    )

    __table_args__ = (UniqueConstraint("tenant_id", "billing_period", name="uq_invoice_tenant_period"),)


class InvoiceLineItem(Base, TimestampMixin):
    __tablename__ = "invoice_line_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    invoice_id: Mapped[int] = mapped_column(Integer, ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)  # SOLAR | GRID | TAX | TOTAL | NOTE
    quantity_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    rate_inr_per_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    amount_inr: Mapped[float] = mapped_column(Float, nullable=False)

    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="line_items")