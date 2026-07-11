"""Tests for the HKO weather integration (offline; no live network calls).

Covers:
  * HKOClient transform of raw HKO payloads into canonical Weather/WeatherWarning.
  * The /v1/weather route handler (client monkeypatched).
  * Fail-soft behaviour: a dead HKO feed yields a 500 Error envelope.

Run from the transportation-api dir:
    python -m pytest tests/test_weather.py
"""
import sys
import os

import pytest
from fastapi.testclient import TestClient

# Make the package importable when run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.clients.hko import HKOClient, _severity_for
from models import Weather, WeatherWarning, MultilingualText

# ---------------------------------------------------------------------------
# Fixtures: realistic HKO payloads (mirrors the live API verified during build)
# ---------------------------------------------------------------------------
RHRREAD = {
    "temperature": {
        "data": [
            {"place": "京士柏", "value": 28, "unit": "C"},
            {"place": "香港天文台", "value": 29, "unit": "C"},
        ]
    },
    "humidity": {"recordTime": "2026-07-11T02:00:00+08:00",
                 "data": [{"unit": "percent", "value": 81, "place": "香港天文台"}]},
    "icon": [60],
    "iconUpdateTime": "2026-07-11T01:45:00+08:00",
    "updateTime": "2026-07-11T02:02:00+08:00",
    "warningMessage": ["酷熱天氣警告現正生效。"],
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


def _client_with(monkeypatch, rhrread=None, warnsum=None, warninginfo=None, fnd=None, lang="en"):
    """Return an HKOClient whose _get_json returns canned payloads."""
    payloads = {"rhrread": rhrread, "warnsum": warnsum, "warningInfo": warninginfo, "fnd": fnd}
    client = HKOClient(lang=lang)
    monkeypatch.setattr(client, "_get_json", lambda url, params=None: payloads.get(params["dataType"]))
    return client


# ---------------------------------------------------------------------------
# HKOClient transform tests
# ---------------------------------------------------------------------------
def test_current_weather_transform(monkeypatch):
    client = _client_with(monkeypatch, rhrread=RHRREAD, warnsum=WARNSUM, warninginfo=WARNINGINFO)
    weather = client.get_current_weather()
    assert isinstance(weather, Weather)
    assert weather.temperature == {"place": "香港天文台", "value": 29, "unit": "C"}
    assert weather.humidity == {"value": 81, "unit": "percent"}
    assert weather.icon == [60]
    assert isinstance(weather.update_time, __import__("datetime").datetime)
    assert len(weather.warnings) == 1
    w = weather.warnings[0]
    assert w.code == "WHOT"
    assert w.severity == "warning"
    # Title is multilingual via the static map (en requested, but tc/sc present).
    assert w.title.en == "Very Hot Weather Warning"
    assert w.title.tc == "酷熱天氣警告"
    assert "now in force" in (w.contents or "")


def test_warnings_only(monkeypatch):
    client = _client_with(monkeypatch, warnsum=WARNSUM, warninginfo=WARNINGINFO)
    warnings = client.get_weather_warnings()
    assert len(warnings) == 1
    assert warnings[0].code == "WHOT"
    assert warnings[0].issue_time is not None


def test_severity_classification():
    assert _severity_for("WRAINA") == "amber"
    assert _severity_for("WRAINR") == "red"
    assert _severity_for("WRAINB") == "black"
    assert _severity_for("WTC") == "warning"
    assert _severity_for("WHOT") == "warning"
    assert _severity_for("UNKNOWN") == "warning"


def test_en_temperature_uses_hko_observatory_station(monkeypatch):
    """With lang=en the canonical station is labelled in English; the client
    must still pick 'Hong Kong Observatory', not the first element."""
    en_rhrread = {
        "temperature": {
            "data": [
                {"place": "King's Park", "value": 28, "unit": "C"},
                {"place": "Hong Kong Observatory", "value": 29, "unit": "C"},
            ]
        },
        "humidity": {"data": [{"unit": "percent", "value": 81, "place": "Hong Kong Observatory"}]},
        "icon": [50],
    }
    client = _client_with(monkeypatch, rhrread=en_rhrread)
    weather = client.get_current_weather()
    assert weather is not None
    assert weather.temperature == {"place": "Hong Kong Observatory", "value": 29, "unit": "C"}


def test_tc_temperature_uses_hko_observatory_station(monkeypatch):
    """With lang=tc the canonical station is the Chinese label; still picked."""
    tc_rhrread = {
        "temperature": {
            "data": [
                {"place": "京士柏", "value": 28, "unit": "C"},
                {"place": "香港天文台", "value": 29, "unit": "C"},
            ]
        },
        "humidity": {"data": [{"unit": "percent", "value": 81, "place": "香港天文台"}]},
        "icon": [50],
    }
    client = _client_with(monkeypatch, rhrread=tc_rhrread)
    weather = client.get_current_weather()
    assert weather is not None
    assert weather.temperature == {"place": "香港天文台", "value": 29, "unit": "C"}


def test_fail_soft_on_rhrread_error(monkeypatch):
    client = _client_with(monkeypatch, rhrread=None)
    assert client.get_current_weather() is None


def test_fail_soft_on_warnsum_error(monkeypatch):
    client = _client_with(monkeypatch, warnsum=None)
    assert client.get_weather_warnings() == []


def test_warnings_without_info_text(monkeypatch):
    """warnsum present but warningInfo down -> warnings still returned, no contents."""
    client = _client_with(monkeypatch, warnsum=WARNSUM, warninginfo=None)
    warnings = client.get_weather_warnings()
    assert len(warnings) == 1
    assert warnings[0].contents is None


# ---------------------------------------------------------------------------
# Route handler tests (patch HKOClient._get_json -> no network)
# ---------------------------------------------------------------------------
from app import app as _app  # noqa: E402


def _patch_client(monkeypatch, rhrread=None, warnsum=None, warninginfo=None):
    """Patch HKOClient._get_json so route handlers never hit the network."""
    payloads = {"rhrread": rhrread, "warnsum": warnsum, "warningInfo": warninginfo}
    monkeypatch.setattr(HKOClient, "_get_json", lambda self, url, params=None: payloads.get(params["dataType"]))


def test_get_weather_endpoint(monkeypatch):
    _patch_client(monkeypatch, rhrread=RHRREAD, warnsum=WARNSUM, warninginfo=WARNINGINFO)
    test_client = TestClient(_app)
    r = test_client.get("/v1/weather?lang=en")
    assert r.status_code == 200
    data = r.json()
    assert data["temperature"]["value"] == 29
    assert data["humidity"]["value"] == 81
    # Condition description is resolved from the authoritative HKO icon code
    # (60 -> "Cloudy").
    assert data["description"] == "Cloudy"
    assert len(data["warnings"]) == 1
    assert data["warnings"][0]["code"] == "WHOT"


def test_weather_description_localised(monkeypatch):
    """Same icon code resolves to the requested language's label."""
    client = _client_with(monkeypatch, rhrread=RHRREAD)
    weather = client.get_current_weather()
    assert weather is not None
    # lang=en was requested in _client_with -> English label for icon 60.
    assert weather.description == "Cloudy"


def test_weather_description_tc(monkeypatch):
    payloads = {"rhrread": RHRREAD, "warnsum": WARNSUM, "warningInfo": WARNINGINFO}
    client = HKOClient(lang="tc")
    monkeypatch.setattr(client, "_get_json", lambda url, params=None: payloads.get(params["dataType"]))
    weather = client.get_current_weather()
    assert weather is not None
    assert weather.description == "多雲"


def test_weather_without_icons_has_no_description(monkeypatch):
    no_icon = dict(RHRREAD)
    no_icon["icon"] = []
    client = _client_with(monkeypatch, rhrread=no_icon)
    weather = client.get_current_weather()
    assert weather is not None
    assert weather.description is None


def test_weather_icon_mapping_authoritative(monkeypatch):
    """Icon codes map to the official HKO captions (verified July 2026):
    50 = Sunny, 60 = Cloudy. `lang` selects the language column."""
    sunny = dict(RHRREAD)
    sunny["icon"] = [50]
    client = _client_with(monkeypatch, rhrread=sunny, lang="en")
    w = client.get_current_weather()
    assert w is not None
    assert w.description == "Sunny"

    client_tc = HKOClient(lang="tc")
    monkeypatch.setattr(client_tc, "_get_json", lambda url, params=None: sunny)
    w_tc = client_tc.get_current_weather()
    assert w_tc is not None
    assert w_tc.description == "陽光充沛"

    client_sc = HKOClient(lang="sc")
    monkeypatch.setattr(client_sc, "_get_json", lambda url, params=None: sunny)
    w_sc = client_sc.get_current_weather()
    assert w_sc is not None
    assert w_sc.description == "阳光充沛"


def test_weather_endpoint_hko_down_returns_500(monkeypatch):
    """HKO down (rhrread None) -> 500 Error envelope; live behaviour is fail-loud
    at the route so downstream clients get a clear error, not silent empty."""
    _patch_client(monkeypatch, rhrread=None, warnsum=None)
    test_client = TestClient(_app)
    r = test_client.get("/v1/weather")
    assert r.status_code == 500
    assert r.json()["code"] == "UPSTREAM_ERROR"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
