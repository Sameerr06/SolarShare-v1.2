"""
Model registry aggregator.

Importing this module guarantees every ORM model in `app/models/` is
registered on `Base.metadata`, which `app/db/init_db.py` relies on before
calling `create_all()`. As later phases add new model modules (e.g.
weather observations, forecasts, allocation results, billing records),
import them here too.
"""

from app.models.estate import Estate  # noqa: F401
from app.models.config import PVConfig, BatteryConfig  # noqa: F401
from app.models.tenant import Tenant  # noqa: F401
from app.models.tariff import Tariff, TariffPeriod, SolarTariffConfig  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.weather import WeatherObservation, NasaPowerCache, SolarGenerationEstimate  # noqa: F401
from app.models.public_load import PublicLoadSeries, PublicLoadObservation  # noqa: F401
from app.models.load_profile import PublicLoadSeriesProfile  # noqa: F401

__all__ = [
    "Estate",
    "PVConfig",
    "BatteryConfig",
    "Tenant",
    "Tariff",
    "TariffPeriod",
    "SolarTariffConfig",
    "User",
    "WeatherObservation",
    "NasaPowerCache",
    "SolarGenerationEstimate",
    "PublicLoadSeries",
    "PublicLoadObservation",
    "PublicLoadSeriesProfile",
]
