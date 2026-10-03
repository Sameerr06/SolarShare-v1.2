"""Pydantic schemas for solar PV generation and configuration endpoints."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict

# Nominal operating cell temperature of a standard crystalline module. Used only
# for the documented cell-temperature estimate below; never presented as measured.
NOCT_CELLS = 45.0


class PVConfigRead(BaseModel):
    id: int
    estate_id: int
    capacity_kw: float
    efficiency: float
    performance_ratio: float
    effective_from: datetime
    is_active: bool
    notes: str
    is_demo: bool = False
    explanatory_note: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SolarGenerationRead(BaseModel):
    """One hourly PV generation record.

    Field provenance is deliberately uneven and typed as Optional where the
    value is not actually measured, so a consumer can never mistake a default
    for a reading:

    measured
        `ghi_wm2`            <- WeatherObservation.allsky_sfc_sw_dwn (NASA POWER)
        `ambient_temperature_c` <- WeatherObservation.t2m
        `pv_energy_kwh`      <- SolarGenerationEstimate.estimated_kwh
        `capacity_kw`, `performance_ratio` <- the PVConfig row the estimate used

    derived (documented model, not measured)
        `cell_temperature_c` <- NOCT estimate from ambient temp + GHI
        `pv_power_kw`        <- average power over the 1-hour interval, which is
                                numerically identical to `pv_energy_kwh` because
                                interval_hours == 1.0 (Energy = Power x Time)

    not available
        `dni_wm2`, `dhi_wm2`     NASA POWER's RE community does not publish
                                 direct/diffuse for this integration.
        `poa_irradiance_wm2`      would need a transposition (Perez/isotropic)
                                 model; GHI is reported instead of inventing one.

    These are None rather than 0.0 on purpose — a zero irradiance reading and an
    absent one mean very different things, and conflating them misrepresents a
    data gap as "no sun".
    """

    estate_id: int
    timestamp_local: datetime
    ghi_wm2: Optional[float] = None
    dni_wm2: Optional[float] = None
    dhi_wm2: Optional[float] = None
    ambient_temperature_c: Optional[float] = None
    cell_temperature_c: Optional[float] = None
    poa_irradiance_wm2: Optional[float] = None
    pv_power_kw: Optional[float] = None
    pv_energy_kwh: Optional[float] = None
    capacity_kw: Optional[float] = None
    performance_ratio: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class SolarGenerationListResponse(BaseModel):
    records: List[SolarGenerationRead]
    total_records: int
    is_demo: bool
    explanatory_note: str
