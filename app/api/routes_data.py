"""
Data ingestion endpoints (Phase 2, NASA POWER scope only).

Admin-only: triggering external data ingestion is an estate-management
action, not something tenant users should be able to invoke.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.estate import Estate
from app.schemas.nasa_power import NasaPowerIngestRequest, NasaPowerIngestResponse
from app.services.nasa_power_ingestion import NasaPowerIngestionError, ingest_nasa_power_range

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["data-ingestion"])


@router.post(
    "/nasa-power",
    response_model=NasaPowerIngestResponse,
    dependencies=[Depends(require_role(UserRole.ADMIN))],
)
def trigger_nasa_power_ingestion(
    payload: NasaPowerIngestRequest,
    db: Session = Depends(get_db),
) -> NasaPowerIngestResponse:
    estate = db.get(Estate, payload.estate_id)
    if estate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Estate not found")

    try:
        result = ingest_nasa_power_range(
            db=db,
            estate=estate,
            start_date=payload.start_date,
            end_date=payload.end_date,
            use_cache=payload.use_cache,
        )
    except NasaPowerIngestionError as exc:
        logger.error("NASA POWER ingestion failed for estate_id=%s: %s", estate.id, exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return NasaPowerIngestResponse(estate_id=estate.id, **result)
