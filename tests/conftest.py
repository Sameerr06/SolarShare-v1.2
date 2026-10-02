"""
Shared pytest fixtures.

Tests run against an isolated, in-memory SQLite database (distinct from
whatever `DATABASE_URL` points to in `.env`) so the test suite never
touches a real/dev database file and each test run starts from a clean
schema.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.models import base as _register_models  # noqa: F401  (ensures models are registered)

TEST_DATABASE_URL = "sqlite://"  # in-memory

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    future=True,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine, future=True)


@pytest.fixture(scope="function", autouse=True)
def _reset_database():
    """Create a fresh schema before every test and drop it after."""
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


def _override_get_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client():
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def db_session():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _register_and_login(client, email, password, role, tenant_id=None):
    payload = {"email": email, "password": password, "role": role}
    if tenant_id is not None:
        payload["tenant_id"] = tenant_id
    created = client.post("/api/auth/register", json=payload)
    assert created.status_code == 201, created.text
    login = client.post("/api/auth/login", data={"username": email, "password": password})
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


@pytest.fixture(scope="function")
def admin_token(client):
    """JWT for a freshly registered ADMIN account."""
    return _register_and_login(client, "conftest-admin@example.com", "AdminPass123!", "ADMIN")


@pytest.fixture(scope="function")
def admin_auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="function")
def make_tenant_token(client, db_session):
    """Factory: create the Tenant row if needed, register a TENANT user for it, return its JWT."""
    from app.models.estate import Estate
    from app.models.enums import TenantProfileType
    from app.models.tenant import Tenant

    counter = {"n": 0}

    def _make(tenant_id, tenant_name=None):
        counter["n"] += 1
        tenant = db_session.get(Tenant, tenant_id)
        if tenant is None:
            estate = db_session.query(Estate).order_by(Estate.id).first()
            if estate is None:
                estate = Estate(
                    name="Auth Fixture Estate",
                    latitude=11.0168,
                    longitude=76.9558,
                    timezone="Asia/Kolkata",
                )
                db_session.add(estate)
                db_session.commit()
                db_session.refresh(estate)
            tenant = Tenant(
                id=tenant_id,
                estate_id=estate.id,
                name=tenant_name or f"Test Tenant {tenant_id}",
                profile_type=TenantProfileType.TEXTILE_MANUFACTURING,
            )
            db_session.add(tenant)
            db_session.commit()
            db_session.refresh(tenant)

        return _register_and_login(
            client,
            f"conftest-tenant-{tenant_id}-{counter['n']}@example.com",
            "TenantPass123!",
            "TENANT",
            tenant_id=tenant_id,
        )

    return _make


@pytest.fixture(scope="function")
def tenant_auth(make_tenant_token):
    """Authorization header for a TENANT account bound to tenant_id=1."""
    return {"Authorization": f"Bearer {make_tenant_token(1)}"}
