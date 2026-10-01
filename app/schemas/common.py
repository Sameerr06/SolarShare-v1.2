"""Common Pydantic schemas and mixins across API modules."""

from typing import Optional
from pydantic import BaseModel, Field


class DemoResponseMixin(BaseModel):
    """Mixin for endpoints returning demo/illustrative data."""

    is_demo: bool = Field(
        default=True,
        description="Flag indicating whether response contains prototype demo/placeholder data.",
    )
    explanatory_note: str = Field(
        default="Prototype demo response — model or operational data not yet connected.",
        description="Human-readable explanation of data provenance.",
    )
