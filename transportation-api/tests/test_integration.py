"""Integration smoke test for the Bus ETA API (root integration check).

Run from the transportation-api dir:
    python -m pytest tests/test_integration.py
or:
    python tests/test_integration.py
"""
import sys
import json
import os

import pytest
from fastapi.testclient import TestClient

# Make the package importable when run directly.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# This module is a *contract* test for the combined-endpoint's shape; it runs
# against the built-in mock so it stays deterministic and offline. The live
# provider behaviour is covered separately in test_backend_integration.py.
# Set the flag directly (not via env) because `config.settings` may already be
# imported/cached by another test module in the same pytest session.
from config import settings  # noqa: E402

settings.use_mock_data = True


@pytest.fixture(autouse=True)
def _force_mock():
    """Reset mock flag before every test in this module (per-test, not import)."""
    settings.use_mock_data = True
    yield


from app import app  # noqa: E402

client = TestClient(app)

MOCK_STOP = "946C74E30100FE80"


def test_openapi_merges_all_routers():
    spec = app.openapi()
    paths = spec["paths"]
    # Canonical spec paths (bus-eta-openapi.yaml) must be present ...
    assert "/health" in paths
    assert "/eta" in paths
    assert "/api/v1/bus-stops/{stopId}" in paths
    codes = set(paths["/api/v1/bus-stops/{stopId}"]["get"]["responses"].keys())
    assert {"200", "404", "500"}.issubset(codes)
    # ... and the deprecated /v1/... aliases must still resolve.
    assert "/v1/bus-stops/{stopId}" in paths
    assert "/v1/incidents" in paths
    assert "/v1/weather" in paths
    assert "/v1/weather/warnings" in paths


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_combined_full_payload():
    r = client.get(f"/v1/bus-stops/{MOCK_STOP}")
    assert r.status_code == 200
    data = r.json()
    assert data["stop"]["id"] == MOCK_STOP
    assert len(data["etas"]) == 3
    assert data["weather"] is not None
    assert len(data["incidents"]) == 1
    assert set(data["stop"]["name"].keys()) == {"en", "tc", "sc"}


def test_route_filter():
    r = client.get(f"/v1/bus-stops/{MOCK_STOP}?route=1")
    routes = {e["route"] for e in r.json()["etas"]}
    assert routes == {"1"}


def test_toggles():
    r = client.get(
        f"/v1/bus-stops/{MOCK_STOP}?include_weather=false&include_incidents=false"
    )
    data = r.json()
    assert data["weather"] is None
    assert data["incidents"] == []


def test_unknown_stop_404():
    r = client.get("/v1/bus-stops/DEADBEEF")
    assert r.status_code == 404
    body = r.json()
    assert body["code"] == "RESOURCE_NOT_FOUND"
    assert {"code", "message"} <= set(body.keys())


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
