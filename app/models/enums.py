"""
Shared enumerations used across ORM models.

Kept centralized so Phase 2+ modules (ingestion, forecasting, allocation,
billing) reference the same enums rather than redefining string literals.
"""

import enum


class UserRole(str, enum.Enum):
    ADMIN = "ADMIN"
    TENANT = "TENANT"


class TenantProfileType(str, enum.Enum):
    """
    The six locked SolarShare demo tenant profiles.

    Per the locked specification: these are SolarShare prototype profile
    mappings applied to public load curves — not a claim that any given
    data source "is" an actual business of that type.
    """
    TEXTILE_MANUFACTURING = "TEXTILE_MANUFACTURING"
    FOOD_PROCESSING = "FOOD_PROCESSING"
    ELECTRONICS_MANUFACTURING = "ELECTRONICS_MANUFACTURING"
    PACKAGING_UNIT = "PACKAGING_UNIT"
    GENERAL_MANUFACTURING = "GENERAL_MANUFACTURING"
    ENGINEERING_WORKSHOP = "ENGINEERING_WORKSHOP"


class TariffPeriodName(str, enum.Enum):
    MORNING_PEAK = "MORNING_PEAK"
    EVENING_PEAK = "EVENING_PEAK"
    NORMAL = "NORMAL"
    NIGHT = "NIGHT"
