import httpx
import pytest

from app.integrations.nasa_power import (
    NasaPowerRequestError,
    NasaPowerRequestParams,
    fetch_nasa_power,
)


def _params():
    return NasaPowerRequestParams(
        latitude=11.0168,
        longitude=76.9558,
        start_date="20240101",
        end_date="20240101",
        parameters=["ALLSKY_SFC_SW_DWN"],
    )


def _client_with_transport(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_successful_request_returns_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"properties": {"parameter": {}}})

    client = _client_with_transport(handler)
    result = fetch_nasa_power(_params(), client=client)
    assert result == {"properties": {"parameter": {}}}


def test_client_error_fails_fast_without_retry(monkeypatch):
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(400, text="Bad request: invalid longitude")

    monkeypatch.setattr("app.integrations.nasa_power.time.sleep", lambda s: None)
    client = _client_with_transport(handler)
    with pytest.raises(NasaPowerRequestError):
        fetch_nasa_power(_params(), client=client)
    # 400 errors should not be retried per the client's fail-fast policy
    assert call_count["n"] == 1


def test_server_error_retries_then_raises(monkeypatch):
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        return httpx.Response(503, text="Service unavailable")

    monkeypatch.setattr("app.integrations.nasa_power.time.sleep", lambda s: None)
    client = _client_with_transport(handler)
    with pytest.raises(NasaPowerRequestError):
        fetch_nasa_power(_params(), client=client)
    # Should have attempted settings.nasa_power_max_retries times (default 3)
    assert call_count["n"] == 3


def test_transient_failure_then_success_recovers(monkeypatch):
    call_count = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["n"] += 1
        if call_count["n"] < 2:
            return httpx.Response(503, text="Service unavailable")
        return httpx.Response(200, json={"properties": {"parameter": {"ok": True}}})

    monkeypatch.setattr("app.integrations.nasa_power.time.sleep", lambda s: None)
    client = _client_with_transport(handler)
    result = fetch_nasa_power(_params(), client=client)
    assert result == {"properties": {"parameter": {"ok": True}}}
    assert call_count["n"] == 2


def test_timeout_raises_request_error(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("simulated timeout", request=request)

    monkeypatch.setattr("app.integrations.nasa_power.time.sleep", lambda s: None)
    client = _client_with_transport(handler)
    with pytest.raises(NasaPowerRequestError):
        fetch_nasa_power(_params(), client=client)
