"""API routes for solar generation and tenant load forecasting (Prophet model integration scope)."""

import logging
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_optional_current_user, verify_tenant_access
from app.db.session import get_db
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.forecasting import ForecastDataPoint, SolarForecastResponse, TenantForecastResponse

from app.services.solar_forecasting import generate_solar_forecast
from app.services.tenant_forecasting import generate_tenant_forecast

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/forecasting", tags=["forecasting"])


@router.get("/solar", response_model=SolarForecastResponse)
def get_solar_forecast(
    estate_id: int = Query(1, ge=1),
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
) -> SolarForecastResponse:
    """Get real Prophet 24-hour solar generation forecast."""
    return generate_solar_forecast(db, estate_id=estate_id, hours=hours)


@router.get("/tenants/{tenant_id}", response_model=TenantForecastResponse)
def get_tenant_load_forecast(
    tenant_id: int,
    hours: int = Query(24, ge=1, le=168),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_current_user),
) -> TenantForecastResponse:
    """Get real Prophet tenant load forecast."""
    verify_tenant_access(tenant_id, current_user)
    now = datetime.now().replace(minute=0, second=0, microsecond=0)
    return generate_tenant_forecast(db, tenant_id=tenant_id, hours=hours, start_time=now)

