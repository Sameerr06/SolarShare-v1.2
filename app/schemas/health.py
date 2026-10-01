"""Pydantic schema for the health-check endpoint."""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    app_name: str
    app_env: str
    database: str
