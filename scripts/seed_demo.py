"""
Phase 1 demo seed script.

Creates a minimal Estate + one Tenant row so ADMIN/TENANT registration and
role-based access can be exercised against the live API.

IMPORTANT: this seeds only enough data to test the Phase 1 auth foundation.
It does NOT seed the 6 locked tenant profiles, PV/battery config rows, or
tariff rows — that seeding belongs to the phase that actually consumes
those values (data ingestion / billing), so it isn't duplicated here and
then invalidated later.

Usage:
    PYTHONPATH=. python scripts/seed_demo.py

(Run from the `solarshare-backend/` project root with the venv activated so
the `app` package resolves; PYTHONPATH=. is required since this is a plain
script, not an installed package.)

Must be run as a script (not `python -c ...` importing individual model
modules) or with `app.models.base` imported first, so that every ORM model
is registered on the shared mapper registry before SQLAlchemy resolves
string-based relationship() references (e.g. Estate.pv_configs ->
"PVConfig"). Importing only `app.models.estate` and `app.models.tenant`
directly, without triggering `app.models.base`, is what caused the earlier
`InvalidRequestError: ... failed to locate a name ('PVConfig')` failure
during manual verification — this script exists specifically to avoid that
class of mistake going forward.
"""

import logging
import os
import sys

# Ensure workspace root is in path, so this script runs as
# `python scripts/seed_demo.py` without needing PYTHONPATH=. first.
# (Running a script puts its own directory — `scripts/` — on sys.path,
# not the working directory, so `import app` would otherwise fail.)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.logging_config import configure_logging
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.models import base as _register_all_models  # noqa: F401  (see module docstring)
from sqlalchemy import func
from app.core.security import hash_password
from app.models.enums import TenantProfileType, UserRole
from app.models.estate import Estate
from app.models.tenant import Tenant
from app.models.user import User

configure_logging()
logger = logging.getLogger(__name__)


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        estate = db.query(Estate).filter(Estate.name == "Coimbatore Demo Estate").first()
        if estate is None:
            estate = Estate(name="Coimbatore Demo Estate", latitude=11.0168, longitude=76.9558)
            db.add(estate)
            db.commit()
            db.refresh(estate)
            logger.info("Created estate id=%s", estate.id)
        else:
            logger.info("Estate already exists id=%s", estate.id)

        tenants_to_seed = [
            ("Textile Manufacturing Unit", TenantProfileType.TEXTILE_MANUFACTURING, "T258"),
            ("Food Processing Facility", TenantProfileType.FOOD_PROCESSING, "T11"),
            ("Electronics Assembly", TenantProfileType.ELECTRONICS_MANUFACTURING, "T301"),
            ("Packaging & Plastics Unit", TenantProfileType.PACKAGING_UNIT, "T300"),
            ("General Engineering Works", TenantProfileType.GENERAL_MANUFACTURING, "T84"),
            ("Precision Tooling Workshop", TenantProfileType.ENGINEERING_WORKSHOP, "T3"),
        ]

        seeded_tenants = []
        for name, profile_type, series_id in tenants_to_seed:
            tenant = db.query(Tenant).filter(
                Tenant.estate_id == estate.id,
                Tenant.profile_type == profile_type
            ).first()

            if tenant is None:
                tenant = Tenant(
                    estate_id=estate.id,
                    name=name,
                    profile_type=profile_type,
                    source_client_series_id=series_id,
                )
                db.add(tenant)
                db.commit()
                db.refresh(tenant)
                logger.info("Created tenant: %s (id=%s, series=%s)", name, tenant.id, series_id)
            else:
                if tenant.source_client_series_id != series_id:
                    tenant.source_client_series_id = series_id
                    db.commit()
                    db.refresh(tenant)
                    logger.info("Updated tenant series for %s to %s", name, series_id)
                else:
                    logger.info("Tenant already exists: %s (id=%s)", name, tenant.id)
            seeded_tenants.append(tenant)

        # Seed users for Admin and 6 Tenants
        users_to_seed = [
            ("ADMIN", "4005", UserRole.ADMIN, None),
            ("T258", "101", UserRole.TENANT, seeded_tenants[0].id),
            ("T11", "102", UserRole.TENANT, seeded_tenants[1].id),
            ("T301", "103", UserRole.TENANT, seeded_tenants[2].id),
            ("T300", "104", UserRole.TENANT, seeded_tenants[3].id),
            ("T84", "105", UserRole.TENANT, seeded_tenants[4].id),
            ("T3", "106", UserRole.TENANT, seeded_tenants[5].id),
        ]

        for username, plain_pass, role, tenant_id in users_to_seed:
            user = db.query(User).filter(func.lower(User.email) == username.lower()).first()
            if user is None:
                user = User(
                    email=username,
                    hashed_password=hash_password(plain_pass),
                    role=role,
                    tenant_id=tenant_id,
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                logger.info("Created user: %s (id=%s, role=%s, tenant_id=%s)", username, user.id, role.value, tenant_id)
            else:
                user.hashed_password = hash_password(plain_pass)
                user.role = role
                user.tenant_id = tenant_id
                db.commit()
                logger.info("Updated user: %s", username)

        print(f"ESTATE_ID={estate.id}")
        for t in seeded_tenants:
            print(f"TENANT_ID={t.id} NAME='{t.name}' PROFILE={t.profile_type.value} SERIES={t.source_client_series_id}")
    finally:
        db.close()


if __name__ == "__main__":
    seed()

