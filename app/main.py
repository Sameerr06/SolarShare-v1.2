"""
SolarShare backend — FastAPI application entrypoint.

Phase 1 scope only: foundational structure, config, database, auth
(ADMIN/TENANT), health check. No domain logic (ingestion, forecasting,
optimization, billing, invoicing) is implemented here — see the locked
specification's phase plan for what belongs in later phases.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes_allocation import router as allocation_router
from app.api.routes_analytics import router as analytics_router
from app.api.routes_auth import router as auth_router
from app.api.routes_battery import router as battery_router
from app.api.routes_billing import router as billing_router
from app.api.routes_dashboard import router as dashboard_router
from app.api.routes_data import router as data_router
from app.api.routes_demo import router as demo_router
from app.api.routes_estate import router as estate_router
from app.api.routes_forecasting import router as forecasting_router
from app.api.routes_health import router as health_router
from app.api.routes_invoices import router as invoices_router
from app.api.routes_load_profiles import router as load_profiles_router
from app.api.routes_solar import router as solar_router
from app.core.config import settings
from app.core.logging_config import configure_logging
from app.db.init_db import init_db

configure_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s (%s)", settings.app_name, settings.app_env)
    init_db()
    yield
    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    description=(
        "SolarShare — Shared Solar Energy Forecasting, Fair Allocation and "
        "Time-of-Use Billing Platform for MSME Industrial Estates."
    ),
    version="0.2.0-phase2",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    logger.warning("Validation error on %s %s: %s", request.method, request.url.path, exc.errors())
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=jsonable_encoder({"detail": exc.errors()}),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error."},
    )


app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(demo_router, prefix="/api")
app.include_router(estate_router, prefix="/api")
app.include_router(data_router, prefix="/api")
app.include_router(load_profiles_router, prefix="/api")
app.include_router(solar_router, prefix="/api")
app.include_router(forecasting_router, prefix="/api")
app.include_router(allocation_router, prefix="/api")
app.include_router(battery_router, prefix="/api")
app.include_router(billing_router, prefix="/api")
app.include_router(invoices_router, prefix="/api")
app.include_router(analytics_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")


@app.get("/")
def root() -> dict:
    return {
        "app": settings.app_name,
        "phase": "Phase 1 — Foundational Architecture",
        "docs": "/docs",
    }
