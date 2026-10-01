"""Pydantic schemas for the NASA POWER data-ingestion endpoint."""

from datetime import date

from pydantic import BaseModel, Field, model_validator


class NasaPowerIngestRequest(BaseModel):
    estate_id: int
    start_date: date
    end_date: date
    use_cache: bool = True

    @model_validator(mode="after")
    def validate_date_range(self) -> "NasaPowerIngestRequest":
        if self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        return self


class NasaPowerIngestResponse(BaseModel):
    estate_id: int
    records_written: int
    data_status: str
    cache_hit: bool
