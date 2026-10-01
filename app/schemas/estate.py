"""
Pydantic schemas for Estate entities and weather-correlation location
management.

`EstateRead` exposes `weather_observation_count` / `solar_generation_estimate_count`
so a client can tell, without a second round trip, whether an estate actually has
data for its coordinates yet — important when coordinates are switched, because
the new location starts with zero rows until a sync runs.
"""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EstateBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    timezone: str = Field(default="Asia/Kolkata", max_length=64)


class EstateCreate(EstateBase):
    pass


class EstateUpdate(BaseModel):
    """Partial update — every field optional so a client can change only coords."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    timezone: Optional[str] = Field(default=None, max_length=64)


class EstateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    latitude: float
    longitude: float
    timezone: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    weather_observation_count: int = 0
    solar_generation_estimate_count: int = 0

    @property
    def has_data(self) -> bool:
        return self.weather_observation_count > 0


class EstatePreset(BaseModel):
    """
    A ready-made location the operator can switch to.

    These are convenience shortcuts only — every value is an ordinary
    latitude/longitude that the operator may also type manually, so no
    business logic anywhere may assume an estate is one of these presets.
    """

    id: str
    name: str
    region: str
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    timezone: str = "Asia/Kolkata"
    description: str = ""


class EstateSyncWeatherRequest(BaseModel):
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    use_cache: bool = True

    @model_validator(mode="after")
    def validate_date_range(self) -> "EstateSyncWeatherRequest":
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must not be after end_date")
        return self


class EstateSyncWeatherResponse(BaseModel):
    estate_id: int
    latitude: float
    longitude: float
    start_date: date
    end_date: date
    records_written: int
    generation_estimates_written: int
    data_status: str
    cache_hit: bool
    pv_config_id: Optional[int] = None
    stale_rows_removed: int = 0
    message: str

    # Data-quality signal. NASA POWER returns its fill value (-999) for hours it
    # has not processed yet, so a window inside the source's latency returns
    # records whose GHI is NULL. Exposing the split lets the UI say so plainly
    # instead of rendering a silently empty chart.
    hours_with_ghi: int = 0
    hours_missing_ghi: int = 0
    warning: Optional[str] = None


PRESET_ESTATES: List[EstatePreset] = [
    EstatePreset(
        id="coimbatore-msme",
        name="Coimbatore MSME Estate",
        region="Tamil Nadu",
        latitude=11.0168,
        longitude=76.9558,
        description="Textile, casting, and precision engineering MSME manufacturing cluster.",
    ),
    EstatePreset(
        id="chennai-guindy",
        name="Chennai Guindy Industrial Estate",
        region="Tamil Nadu",
        latitude=13.0067,
        longitude=80.2206,
        description="One of India's oldest multi-product MSME industrial estates in Chennai.",
    ),
    EstatePreset(
        id="bengaluru-peenya",
        name="Bengaluru Peenya Industrial Area",
        region="Karnataka",
        latitude=13.0299,
        longitude=77.5199,
        description="South Asia's largest industrial estate housing over 5,000 MSME units.",
    ),
    EstatePreset(
        id="pune-bhosari",
        name="Pune Bhosari MIDC",
        region="Maharashtra",
        latitude=18.7519,
        longitude=73.8537,
        description="Automotive engineering, machine tooling, and fabrication cluster.",
    ),
    EstatePreset(
        id="ahmedabad-vatva",
        name="Ahmedabad Vatva GIDC",
        region="Gujarat",
        latitude=22.9667,
        longitude=72.4667,
        description="Chemical, dye, machinery, and renewable power manufacturing hub.",
    ),
    EstatePreset(
        id="hyderabad-cherlapally",
        name="Hyderabad Cherlapally IDA",
        region="Telangana",
        latitude=17.3167,
        longitude=78.5333,
        description="Industrial development area featuring electronics, plastics, and pharma MSMEs.",
    ),
    EstatePreset(
        id="bhadla-solar-park",
        name="Bhadla Mega Solar Park",
        region="Rajasthan",
        latitude=27.5333,
        longitude=71.9167,
        description="World's largest operational solar park (~2,245 MW) in the Thar Desert.",
    ),
    EstatePreset(
        id="charanka-solar-park",
        name="Charanka Solar Park",
        region="Gujarat",
        latitude=23.85,
        longitude=71.6333,
        description="Gujarat's pioneer utility-scale solar hub in Patan district.",
    ),
    EstatePreset(
        id="delhi-okhla",
        name="Delhi Okhla Industrial Area",
        region="Delhi",
        latitude=28.4728,
        longitude=77.2075,
        description="North Indian commercial & light industrial manufacturing precinct.",
    ),
    EstatePreset(
        id="mumbai-thane",
        name="Mumbai Thane-Belapur MIDC",
        region="Maharashtra",
        latitude=19.2183,
        longitude=72.9781,
        description="Prominent trans-Thane corridor for heavy engineering and tech parks.",
    ),
]