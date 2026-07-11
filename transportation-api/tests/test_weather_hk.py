"""Tests for the /api/v1/weather/hk endpoint (offline; no live network calls).

Covers:
  * WeatherApiService + HKOClient transform (data structure correctness).
  * Endpoint-level TTL caching: the HKO client is invoked at most once per
    (lang, include_forecast) variant and a cached copy is served on repeat.
  * Cache isolation: forecast enrichment never mutates the stored entry.
  * Route handler (integration): correct JSON structure, language variants,
    caching across requests, and error handling when HKO is down.

Run from the transportation-api dir:
    python -m pytest tests/test_weather_hk.py
"""
import sys
import os

import pytest
from fastapi.testclient import TestClient

# Make the package importable when run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.clients.hko import HKOClient
from src.services import WeatherApiService
from models import Weather, WeatherWarning, ForecastDay

# ---------------------------------------------------------------------------
# Fixtures: realistic HKO payloads (mirrors the live API verified during build)
# ---------------------------------------------------------------------------
RHRREAD = {
    "temperature": {
        "data": [
            {"place": "King's Park", "value": 28, "unit": "C"},
            {"place": "Hong Kong Observatory", "value": 29, "unit": "C"},
        ]
    },
    "humidity": {"data": [{"unit": "percent", "value": 81, "place": "Hong Kong Observatory"}]},
    "icon": [50],
    "iconUpdateTime": "2026-07-11T01:45:00+08:00",
    "updateTime": "2026-07-11T02:02:00+08:00",
    "warningMessage": ["Very Hot Weather Warning is in force."],
}

WARNSUM = {
    "WHOT": {"name": "Very Hot Weather Warning", "code": "WHOT",
             "actionCode": "REISSUE", "issueTime": "2026-07-10T11:30:00+08:00",
             "updateTime": "2026-07-10T16:20:00+08:00"}
}

WARNINGINFO = {
    "details": [
        {"contents": ["The Very Hot Weather Warning is now in force.", "Stay hydrated."],
         "warningStatementCode": "WHOT", "updateTime": "2026-07-10T16:20:00+08:00"}
    ]
}

FND = {
    "weatherForecast": [
        {"forecastDate": "20260711", "week": "Saturday", "forecastWeather": "Sunny",
         "forecastMaxtemp": {"value": 33}, "forecastMintemp": {"value": 28}},
        {"forecastDate": "20260712", "week": "Sunday", "forecastWeather": "Cloudy",
         "forecastMaxtemp": {"value": 31}, "forecastMintemp": {"value": 27}},
    ]
}


def _service_with(monkeypatch, rhrread=RHRREAD, warnsum=WARNSUM, warninginfo=WARNINGINFO, fnd=FND, ttl=600):
    """Return a WeatherApiService whose underlying client returns canned data."""
    payloads = {"rhrread": rhrread, "warnsum": warnsum, "warningInfo": warninginfo, "fnd": fnd}
    # Patch HKOClient._get_json globally so every client the service builds is canned.
    monkeypatch.setattr(
        HKOClient, "_get_json",
        lambda self, url, params=None: payloads.get(params["dataType"]),
    )
    return WeatherApiService(cache_ttl=ttl)


# ---------------------------------------------------------------------------
# Service transform / data-structure tests
# ---------------------------------------------------------------------------
def test_service_returns_canonical_weather(monkeypatch):
    svc = _service_with(monkeypatch)
    w = svc.get_weather(lang="en")
    assert isinstance(w, Weather)
    assert w.temperature == {"place": "Hong Kong Observatory", "value": 29, "unit": "C"}
    assert w.humidity == {"value": 81, "unit": "percent"}
    assert w.icon == [50]
    assert w.description == "Sunny"  # icon 50 -> Sunny (en)
    assert isinstance(w.update_time, __import__("datetime").datetime)
    assert len(w.warnings) == 1
    assert w.warnings[0].code == "WHOT"


def test_service_language_variants(monkeypatch):
    svc = _service_with(monkeypatch)
    assert svc.get_weather(lang="en").description == "Sunny"
    assert svc.get_weather(lang="tc").description == "陽光充沛"
    assert svc.get_weather(lang="sc").description == "阳光充沛"


def test_service_forecast_enrichment(monkeypatch):
    svc = _service_with(monkeypatch)
    w = svc.get_weather(lang="en", include_forecast=True)
    assert w.forecast is not None
    assert len(w.forecast) == 2
    assert all(isinstance(d, ForecastDay) for d in w.forecast)
    assert w.forecast[0].date == "20260711"
    assert w.forecast[0].max_temp == 33


def test_service_warnings(monkeypatch):
    svc = _service_with(monkeypatch)
    warnings = svc.get_warnings(lang="en")
    assert isinstance(warnings, list)
    assert all(isinstance(x, WeatherWarning) for x in warnings)
    assert warnings[0].code == "WHOT"
    assert warnings[0].severity == "warning"


# ---------------------------------------------------------------------------
# Caching behaviour
# ---------------------------------------------------------------------------
def test_cache_avoids_repeat_upstream_calls(monkeypatch):
    svc = _service_with(monkeypatch)
    calls = {"n": 0}
    orig = HKOClient.get_current_weather

    def counting(self, *a, **k):
        calls["n"] += 1
        return orig(self, *a, **k)

    monkeypatch.setattr(HKOClient, "get_current_weather", counting)

    svc.get_weather(lang="en")
    svc.get_weather(lang="en")          # cache hit
    svc.get_weather(lang="en")          # cache hit
    # Exactly one upstream fetch for the (en, False) variant.
    assert calls["n"] == 1


def test_cache_keyed_by_lang(monkeypatch):
    svc = _service_with(monkeypatch)
    calls = {"n": 0}
    orig = HKOClient.get_current_weather

    def counting(self, *a, **k):
        calls["n"] += 1
        return orig(self, *a, **k)

    monkeypatch.setattr(HKOClient, "get_current_weather", counting)

    svc.get_weather(lang="en")
    svc.get_weather(lang="tc")          # distinct variant -> new fetch
    svc.get_weather(lang="en")          # still cached
    assert calls["n"] == 2


def test_cache_keyed_by_forecast_flag(monkeypatch):
    svc = _service_with(monkeypatch)
    calls = {"n": 0}
    orig = HKOClient.get_current_weather

    def counting(self, *a, **k):
        calls["n"] += 1
        return orig(self, *a, **k)

    monkeypatch.setattr(HKOClient, "get_current_weather", counting)

    svc.get_weather(lang="en", include_forecast=False)
    svc.get_weather(lang="en", include_forecast=True)   # distinct variant
    svc.get_weather(lang="en", include_forecast=False)  # cached
    assert calls["n"] == 2


def test_cache_copy_not_mutated_by_forecast(monkeypatch):
    """Attaching a forecast to a returned copy must not poison the cached entry."""
    svc = _service_with(monkeypatch)
    first = svc.get_weather(lang="en", include_forecast=False)
    assert first.forecast is None
    # Mutate the returned object.
    first.forecast = [ForecastDay(date="20990101", week="X")]
    # A fresh cached read must still have no forecast (and vice-versa).
    second = svc.get_weather(lang="en", include_forecast=False)
    assert second.forecast is None
    # Now request with forecast -> populated, and the no-forecast cache is intact.
    third = svc.get_weather(lang="en", include_forecast=True)
    assert third.forecast is not None and len(third.forecast) == 2
    fourth = svc.get_weather(lang="en", include_forecast=False)
    assert fourth.forecast is None


def test_clear_cache_forces_refetch(monkeypatch):
    svc = _service_with(monkeypatch)
    calls = {"n": 0}
    orig = HKOClient.get_current_weather

    def counting(self, *a, **k):
        calls["n"] += 1
        return orig(self, *a, **k)

    monkeypatch.setattr(HKOClient, "get_current_weather", counting)

    svc.get_weather(lang="en")
    svc.clear_cache()
    svc.get_weather(lang="en")
    assert calls["n"] == 2


def test_cache_expiry(monkeypatch):
    """With a 0s TTL the entry expires immediately and a second read refetches."""
    svc = _service_with(monkeypatch, ttl=0)
    calls = {"n": 0}
    orig = HKOClient.get_current_weather

    def counting(self, *a, **k):
        calls["n"] += 1
        return orig(self, *a, **k)

    monkeypatch.setattr(HKOClient, "get_current_weather", counting)

    svc.get_weather(lang="en")
    svc.get_weather(lang="en")
    assert calls["n"] == 2


# ---------------------------------------------------------------------------
# Integration (route handler) tests — no network
# ---------------------------------------------------------------------------
from app import app as _app  # noqa: E402
from routes.weather_hk import _service as _route_service  # noqa: E402


@pytest.fixture(autouse=True)
def _clear_route_cache():
    """The route uses a module-level service singleton whose cache persists
    across the whole session; clear it before each test so HKO-down scenarios
    actually reach the (mocked) client instead of hitting a stale good cache."""
    _route_service.clear_cache()
    yield
    _route_service.clear_cache()


@pytest.fixture
def client():
    return TestClient(_app)


def test_endpoint_returns_weather_json(client, monkeypatch):
    _service_with(monkeypatch)
    r = client.get("/api/v1/weather/hk?lang=en")
    assert r.status_code == 200
    data = r.json()
    assert data["temperature"]["value"] == 29
    assert data["temperature"]["place"] == "Hong Kong Observatory"
    assert data["humidity"]["value"] == 81
    assert data["description"] == "Sunny"
    assert data["icon"] == [50]
    assert len(data["warnings"]) == 1
    assert data["warnings"][0]["code"] == "WHOT"
    assert data["warnings"][0]["severity"] == "warning"


def test_endpoint_language_variants(client, monkeypatch):
    _service_with(monkeypatch)
    assert client.get("/api/v1/weather/hk?lang=en").json()["description"] == "Sunny"
    assert client.get("/api/v1/weather/hk?lang=tc").json()["description"] == "陽光充沛"
    assert client.get("/api/v1/weather/hk?lang=sc").json()["description"] == "阳光充沛"


def test_endpoint_with_forecast(client, monkeypatch):
    _service_with(monkeypatch)
    r = client.get("/api/v1/weather/hk?lang=en&include_forecast=true")
    assert r.status_code == 200
    data = r.json()
    assert data["forecast"] is not None
    assert len(data["forecast"]) == 2
    assert data["forecast"][0]["max_temp"] == 33


def test_endpoint_caches_across_requests(client, monkeypatch):
    calls = {"n": 0}
    payloads = {"rhrread": RHRREAD, "warnsum": WARNSUM, "warningInfo": WARNINGINFO, "fnd": FND}
    orig = HKOClient.get_current_weather

    def counting(self, *a, **k):
        calls["n"] += 1
        return orig(self, *a, **k)

    monkeypatch.setattr(HKOClient, "get_current_weather", counting)
    # Seed the service cache via the route-level singleton by issuing requests.
    client.get("/api/v1/weather/hk?lang=en")
    client.get("/api/v1/weather/hk?lang=en")
    # Only one upstream fetch because the route shares one service instance/cache.
    assert calls["n"] == 1


def test_endpoint_warnings_subroute(client, monkeypatch):
    _service_with(monkeypatch)
    r = client.get("/api/v1/weather/hk/warnings?lang=en")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["code"] == "WHOT"


def test_endpoint_hko_down_returns_500(client, monkeypatch):
    """Core feed down -> 500 UPSTREAM_ERROR envelope (fail-loud, not silent)."""
    payloads = {"rhrread": None, "warnsum": None, "warningInfo": None, "fnd": None}
    monkeypatch.setattr(
        HKOClient, "_get_json",
        lambda self, url, params=None: payloads.get(params["dataType"]),
    )
    r = client.get("/api/v1/weather/hk?lang=en")
    assert r.status_code == 500
    body = r.json()
    assert body["code"] == "UPSTREAM_ERROR"
    assert {"code", "message"} <= set(body.keys())


def test_endpoint_warnings_degrade_on_feed_down(client, monkeypatch):
    """Warnings sub-feed down -> empty list (200), not an error."""
    payloads = {"rhrread": RHRREAD, "warnsum": None, "warningInfo": None, "fnd": FND}
    monkeypatch.setattr(
        HKOClient, "_get_json",
        lambda self, url, params=None: payloads.get(params["dataType"]),
    )
    r = client.get("/api/v1/weather/hk/warnings?lang=en")
    assert r.status_code == 200
    assert r.json() == []


def test_endpoint_openapi_registered(client):
    spec = client.app.openapi()
    paths = spec["paths"]
    assert "/api/v1/weather/hk" in paths
    assert "/api/v1/weather/hk/warnings" in paths


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
