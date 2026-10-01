from sqlalchemy import inspect

from tests.conftest import test_engine

EXPECTED_TABLES = {
    "estates",
    "pv_configs",
    "battery_configs",
    "tenants",
    "tariffs",
    "tariff_periods",
    "solar_tariff_configs",
    "users",
}


def test_all_core_tables_created(_reset_database):
    inspector = inspect(test_engine)
    table_names = set(inspector.get_table_names())
    missing = EXPECTED_TABLES - table_names
    assert not missing, f"Missing expected tables: {missing}"


def test_estate_and_tenant_can_be_persisted(db_session):
    from app.models.estate import Estate
    from app.models.tenant import Tenant
    from app.models.enums import TenantProfileType

    estate = Estate(name="Coimbatore Demo Estate", latitude=11.0168, longitude=76.9558)
    db_session.add(estate)
    db_session.commit()
    db_session.refresh(estate)

    tenant = Tenant(
        estate_id=estate.id,
        name="Textile Manufacturing",
        profile_type=TenantProfileType.TEXTILE_MANUFACTURING,
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)

    assert tenant.id is not None
    assert tenant.estate_id == estate.id
    assert tenant.profile_type == TenantProfileType.TEXTILE_MANUFACTURING
