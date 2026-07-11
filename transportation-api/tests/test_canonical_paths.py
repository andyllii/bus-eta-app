"""Contract tests for the canonical /api/v1/... spec endpoints.

These verify that the paths defined in bus-eta-openapi.yaml are actually
mounted and behave per-spec, and that the deprecated /v1/... aliases remain
available. They run against the built-in mock (offline) so they stay
deterministic in CI.
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from config import settings  # noqa: E402


@pytest.fixture(autouse=True)
def _force_mock(monkeypatch):
    # Scope mock mode to this test only so it cannot leak into other
    # modules' service tests (which inject their own stub clients and rely
    # on live/mock being OFF to exercise those stubs).
    monkeypatch.setattr(settings, "use_mock_data", True)
    yield


from app import app  # noqa: E402

STOP_ID = "946C74E30100FE80"

client = TestClient(app)

# Canonical spec paths per bus-eta-openapi.yaml.
CANONICAL = [
    "/api/v1/eta?route=1&stop=946C74E30100FE80",
    "/api/v1/bus-stops/946C74E30100FE80",
    "/api/v1/weather",
    "/api/v1/weather/warnings",
    "/api/v1/incidents",
    "/api/v1/search?q=1",
]
LEGACY_ALIASES = [
    "/v1/bus-stops/946C74E30100FE80",
    "/v1/weather",
    "/v1/weather/warnings",
    "/v1/incidents",
]


def test_canonical_spec_paths_serve_200():
    for path in CANONICAL:
        r = client.get(path)
        assert r.status_code == 200, f"{path} -> {r.status_code}"


def test_legacy_alias_paths_serve_200():
    for path in LEGACY_ALIASES:
        r = client.get(path)
        assert r.status_code == 200, f"{path} -> {r.status_code}"


def _path_present(base: str, paths) -> bool:
    if base in paths:
        return True
    # Templated dynamic segments (e.g. /api/v1/bus-stops/{stopId}).
    prefix, _, seg = base.rpartition("/")
    if seg and f"{prefix}/{{stopId}}" in paths:
        return True
    return False


def test_openapi_lists_canonical_and_alias_paths():
    # FastAPI memoizes the generated OpenAPI schema on first call; force a
    # regenerate so we always reflect the currently-imported routers.
    app.openapi_schema = None  # type: ignore[attr-defined]
    spec = app.openapi()
    paths = spec["paths"]
    for p in CANONICAL:
        base = p.split("?")[0]
        assert _path_present(base, paths), f"missing canonical {base}"
    for p in LEGACY_ALIASES:
        assert _path_present(p, paths), f"missing alias {p}"


def test_weather_warnings_shape():
    r = client.get("/api/v1/weather/warnings")
    assert r.status_code == 200
    body = r.json()
    assert "warnings" in body
    assert isinstance(body["warnings"], list)


def test_bus_stops_canonical_matches_alias_body():
    """The canonical and legacy bus-stop endpoints must return the same data."""
    canonical = client.get("/api/v1/bus-stops/946C74E30100FE80").json()
    legacy = client.get("/v1/bus-stops/946C74E30100FE80").json()
    assert canonical["stop"]["id"] == legacy["stop"]["id"]
    assert canonical["stop"]["id"] == "946C74E30100FE80"
