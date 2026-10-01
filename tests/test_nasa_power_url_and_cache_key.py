import pytest

from app.integrations.nasa_power import (
    NasaPowerRequestParams,
    NasaPowerValidationError,
    build_cache_key,
)


def _params(**overrides):
    defaults = dict(
        latitude=11.0168,
        longitude=76.9558,
        start_date="20240101",
        end_date="20240102",
        parameters=["ALLSKY_SFC_SW_DWN", "T2M", "RH2M", "WS10M"],
    )
    defaults.update(overrides)
    return NasaPowerRequestParams(**defaults)


def test_url_contains_coimbatore_coordinates():
    url = _params().build_url()
    assert "latitude=11.0168" in url
    assert "longitude=76.9558" in url


def test_url_contains_re_community_by_default():
    url = _params().build_url()
    assert "community=RE" in url


def test_url_contains_utc_time_standard_by_default():
    url = _params().build_url()
    assert "time-standard=UTC" in url


def test_url_contains_all_requested_parameters():
    url = _params().build_url()
    assert "parameters=ALLSKY_SFC_SW_DWN,T2M,RH2M,WS10M" in url


def test_url_contains_start_and_end_dates():
    url = _params().build_url()
    assert "start=20240101" in url
    assert "end=20240102" in url


def test_url_uses_configured_base_url():
    url = _params().build_url()
    assert url.startswith("https://power.larc.nasa.gov/api/temporal/hourly/point?")


def test_url_format_is_json():
    url = _params().build_url()
    assert "format=JSON" in url


def test_invalid_date_format_rejected():
    with pytest.raises(NasaPowerValidationError):
        _params(start_date="2024-01-01")


def test_start_after_end_rejected():
    with pytest.raises(NasaPowerValidationError):
        _params(start_date="20240110", end_date="20240101")


def test_empty_parameters_rejected():
    with pytest.raises(NasaPowerValidationError):
        _params(parameters=[])


def test_cache_key_is_deterministic():
    key1 = _params().cache_key()
    key2 = _params().cache_key()
    assert key1 == key2


def test_cache_key_differs_for_different_location():
    key1 = _params(latitude=11.0168, longitude=76.9558).cache_key()
    key2 = _params(latitude=13.0827, longitude=80.2707).cache_key()  # Chennai
    assert key1 != key2


def test_cache_key_differs_for_different_date_range():
    key1 = _params(start_date="20240101", end_date="20240102").cache_key()
    key2 = _params(start_date="20240201", end_date="20240202").cache_key()
    assert key1 != key2


def test_cache_key_differs_for_different_parameters():
    key1 = _params(parameters=["ALLSKY_SFC_SW_DWN"]).cache_key()
    key2 = _params(parameters=["ALLSKY_SFC_SW_DWN", "T2M"]).cache_key()
    assert key1 != key2


def test_cache_key_stable_regardless_of_parameter_order():
    key1 = _params(parameters=["ALLSKY_SFC_SW_DWN", "T2M"]).cache_key()
    key2 = _params(parameters=["T2M", "ALLSKY_SFC_SW_DWN"]).cache_key()
    assert key1 == key2


def test_build_cache_key_helper_matches_request_params_method():
    p = _params()
    assert build_cache_key(
        latitude=p.latitude,
        longitude=p.longitude,
        parameters=p.parameters,
        start_date=p.start_date,
        end_date=p.end_date,
        community=p.community,
        time_standard=p.time_standard,
    ) == p.cache_key()
