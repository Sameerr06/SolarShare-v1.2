from app.core.config import get_settings


def test_settings_load_without_error():
    settings = get_settings()
    assert settings.app_name == "SolarShare"
    assert settings.jwt_algorithm == "HS256"
    assert settings.access_token_expire_minutes > 0


def test_cors_origins_parsed_as_list():
    settings = get_settings()
    origins = settings.cors_origins_list
    assert isinstance(origins, list)
    assert all(isinstance(o, str) for o in origins)


def test_is_sqlite_detection():
    settings = get_settings()
    assert settings.is_sqlite is True  # Phase 1 default is sqlite:///./solarshare.db
