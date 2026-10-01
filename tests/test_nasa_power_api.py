from app.models.estate import Estate
from app.services import nasa_power_ingestion as ingestion_module


def _register_and_login_admin(client):
    client.post(
        "/api/auth/register",
        json={"email": "admin@example.com", "password": "AdminPass123!", "role": "ADMIN"},
    )
    token = client.post(
        "/api/auth/login",
        data={"username": "admin@example.com", "password": "AdminPass123!"},
    ).json()["access_token"]
    return token


def _register_and_login_tenant(client, tenant_id):
    client.post(
        "/api/auth/register",
        json={
            "email": "tenant@example.com",
            "password": "TenantPass123!",
            "role": "TENANT",
            "tenant_id": tenant_id,
        },
    )
    token = client.post(
        "/api/auth/login",
        data={"username": "tenant@example.com", "password": "TenantPass123!"},
    ).json()["access_token"]
    return token


def _fake_raw_response():
    return {
        "properties": {
            "parameter": {
                "ALLSKY_SFC_SW_DWN": {"2024010100": 0.0},
                "T2M": {"2024010100": 23.0},
                "RH2M": {"2024010100": 80.0},
                "WS10M": {"2024010100": 2.1},
            }
        }
    }


def test_ingestion_endpoint_requires_admin(client, db_session, monkeypatch):
    estate = Estate(name="Coimbatore Demo Estate", latitude=11.0168, longitude=76.9558)
    db_session.add(estate)
    db_session.commit()
    db_session.refresh(estate)

    from app.models.tenant import Tenant
    from app.models.enums import TenantProfileType

    tenant = Tenant(estate_id=estate.id, name="Textile Manufacturing", profile_type=TenantProfileType.TEXTILE_MANUFACTURING)
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    tenant_token = _register_and_login_tenant(client, tenant.id)

    resp = client.post(
        "/api/data/nasa-power",
        json={"estate_id": estate.id, "start_date": "2024-01-01", "end_date": "2024-01-01"},
        headers={"Authorization": f"Bearer {tenant_token}"},
    )
    assert resp.status_code == 403


def test_ingestion_endpoint_succeeds_for_admin(client, db_session, monkeypatch):
    estate = Estate(name="Coimbatore Demo Estate", latitude=11.0168, longitude=76.9558)
    db_session.add(estate)
    db_session.commit()
    db_session.refresh(estate)

    monkeypatch.setattr(ingestion_module, "fetch_nasa_power", lambda params: _fake_raw_response())

    admin_token = _register_and_login_admin(client)
    resp = client.post(
        "/api/data/nasa-power",
        json={"estate_id": estate.id, "start_date": "2024-01-01", "end_date": "2024-01-01"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["records_written"] == 1
    assert body["data_status"] == "LIVE"


def test_ingestion_endpoint_404_for_unknown_estate(client, monkeypatch):
    admin_token = _register_and_login_admin(client)
    resp = client.post(
        "/api/data/nasa-power",
        json={"estate_id": 9999, "start_date": "2024-01-01", "end_date": "2024-01-01"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 404


def test_ingestion_endpoint_rejects_invalid_date_range(client, db_session):
    estate = Estate(name="Coimbatore Demo Estate", latitude=11.0168, longitude=76.9558)
    db_session.add(estate)
    db_session.commit()
    db_session.refresh(estate)

    admin_token = _register_and_login_admin(client)
    resp = client.post(
        "/api/data/nasa-power",
        json={"estate_id": estate.id, "start_date": "2024-01-10", "end_date": "2024-01-01"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 422


def test_ingestion_endpoint_no_token_rejected(client, db_session):
    estate = Estate(name="Coimbatore Demo Estate", latitude=11.0168, longitude=76.9558)
    db_session.add(estate)
    db_session.commit()
    db_session.refresh(estate)

    resp = client.post(
        "/api/data/nasa-power",
        json={"estate_id": estate.id, "start_date": "2024-01-01", "end_date": "2024-01-01"},
    )
    assert resp.status_code == 401
