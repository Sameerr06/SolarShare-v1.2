"""
Centralized configuration management.

All configurable values are read from environment variables (via a `.env`
file in local development). Nothing here should be hardcoded elsewhere in
the application â€” modules that need a setting must import `settings` from
this module.

This keeps Phase 1 consistent with the locked SolarShare specification's
requirement that prototype/config values (PV, battery, tariff, etc., added
in later phases) live in configuration, not inline in business logic.
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- App metadata ---
    app_name: str = "SolarShare"
    app_env: str = "development"
    debug: bool = True

    # --- Database ---
    database_url: str = "sqlite:///./solarshare.db"

    # --- Auth / JWT ---
    jwt_secret_key: str = "change-this-to-a-long-random-secret-in-real-deployments"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # --- Logging ---
    log_level: str = "INFO"

    # --- CORS ---
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # --- NASA POWER integration (Phase 2) ---
    # Base URL for the Hourly Point API. Never hardcode this elsewhere.
    nasa_power_base_url: str = "https://power.larc.nasa.gov/api/temporal/hourly/point"
    nasa_power_community: str = "RE"  # Renewable Energy
    nasa_power_parameters: str = "ALLSKY_SFC_SW_DWN,T2M,RH2M,WS10M"
    nasa_power_time_standard: str = "UTC"
    nasa_power_format: str = "JSON"
    nasa_power_request_timeout_seconds: float = 30.0
    nasa_power_max_retries: int = 3
    nasa_power_retry_backoff_seconds: float = 2.0
    nasa_power_fill_value: float = -999.0
# Measured latency of the Hourly Point API's MERRA-2 derived RE parameters.
    # Observed 2026-10-01: data for 2026-06-15 was present, but 2026-07-01
    # onwards was still entirely fill-value (-999). Syncing "the last few days"
    # therefore returns nothing at all, so the default sync window is back-dated
    # by this many days. Lower it if/when NASA shortens the latency; raise it if
    # the latency grows.
    nasa_power_data_lag_days: int = 120

    # --- Public electricity dataset (Phase 2) ---
    # Source: Zenodo "Electricity Hourly Dataset", DOI 10.5281/zenodo.4656140.
    # This is a PUBLIC PROXY dataset standing in for real Coimbatore MSME
    # smart-meter data â€” never to be presented as the latter. See
    # app/integrations/electricity_dataset.py for the full unit/provenance
    # documentation this configuration supports.
    electricity_dataset_source_name: str = "Electricity Hourly Dataset (Monash/Zenodo)"
    electricity_dataset_source_doi: str = "10.5281/zenodo.4656140"
    electricity_dataset_source_url: str = "https://zenodo.org/records/4656140"
    # Local path to the acquired .tsf file. In an environment with network
    # access to Zenodo, this would be populated by a download step; this
    # sandbox cannot reach zenodo.org, so this defaults to unset and must
    # be provided explicitly (see README for acquisition instructions).
    electricity_dataset_local_path: str = ""
    electricity_dataset_request_timeout_seconds: float = 60.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def nasa_power_parameters_list(self) -> List[str]:
        return [p.strip() for p in self.nasa_power_parameters.split(",") if p.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    """
    Cached settings accessor. Using a function (rather than a bare module
    -level instance) makes it straightforward to override settings in tests
    via dependency overrides or by clearing the cache.
    """
    return Settings()


settings = get_settings()
