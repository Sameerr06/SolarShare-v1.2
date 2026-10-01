"""Pydantic schemas for invoice endpoints."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class InvoiceLineRead(BaseModel):
    id: int
    description: str
    category: str
    quantity_kwh: float
    rate_inr_per_kwh: float
    amount_inr: float

    model_config = ConfigDict(from_attributes=True)


class InvoiceRead(BaseModel):
    id: int
    invoice_number: str
    tenant_id: int
    tenant_name: Optional[str] = None
    billing_period: str
    issue_date: datetime
    due_date: datetime
    status: str
    total_consumption_kwh: float
    solar_consumed_kwh: float
    grid_consumed_kwh: float
    solar_cost_inr: float
    grid_cost_inr: float
    total_bill_inr: float
    savings_inr: float
    line_items: List[InvoiceLineRead] = []
    pdf_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class InvoiceListResponse(BaseModel):
    billing_period: str
    invoices: List[InvoiceRead]
    count: int


class InvoiceGenerateRequest(BaseModel):
    month: str = Field(
        default="2026-08",
        description="Billing period in YYYY-MM format",
        pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
    )