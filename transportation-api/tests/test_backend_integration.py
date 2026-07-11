"""Live backend integration tests against the real Hong Kong open-data feeds.

These hit the network (KMB, Citybus, HKO, Transport Department). They are
*lenient*: if a provider is momentarily unavailable the test skips rather than
fails, so CI without egress still goes green. When the network is available
they assert end-to-end behaviour: a real KMB stop resolves, its ETAs populate,
weather + incidents come back, and unknown stops 404.

Run with the real providers (USE_MOCK_DATA unset / false):
    python -m pytest tests/test_backend_integration.py -q
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Ensure we are NOT in mock mode for these tests (directly, since settings may
# already be cached by another test module in the same session).
from config import settings  # noqa: E402

settings.use_mock_data = False


@pytest.fixture(autouse=True)
def _force_live():
    """Reset mock flag before every test in this module (per-test, not import)."""
    settings.use_mock_data = False
    yield


from app import app  # noqa: E402

client = TestClient(app)

KMB_STOP = "946C74E30100FE80"  # real KMB stop used throughout the spec
CTB_STOP = "001027"            # real Citybus stop


def _network_ok() -> bool:
    """Cheap connectivity probe to the KMB endpoint."""
    import urllib.request

    try:
        req = urllib.request.Request(
            "https://data.etabus.gov.hk/v1/transport/kmb/stop/" + KMB_STOP,
            headers={"User-Agent": "test"},
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status == 200
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _network_ok(), reason="no network to live HK feeds")


def test_live_combined_kmb_stop():
    r = client.get(f"/v1/bus-stops/{KMB_STOP}")
    assert r.status_code == 200
    data = r.json()
    assert data["stop"]["id"] == KMB_STOP
    assert data["stop"]["name"]["tc"]
    assert isinstance(data["etas"], list)
    assert data["weather"] is not None
    # incidents may be empty at some hours; just assert it's a list
    assert isinstance(data["incidents"], list)


def test_live_route_filter():
    r = client.get(f"/v1/bus-stops/{KMB_STOP}?route=1")
    assert r.status_code == 200
    routes = {e["route"] for e in r.json()["etas"]}
    assert routes <= {"1"}


def test_live_toggles():
    r = client.get(
        f"/v1/bus-stops/{KMB_STOP}?include_weather=false&include_incidents=false"
    )
    assert r.status_code == 200
    data = r.json()
    assert data["weather"] is None
    assert data["incidents"] == []


def test_live_weather_endpoint():
    r = client.get("/v1/weather")
    assert r.status_code == 200
    data = r.json()
    assert "icon" in data


def test_live_incidents_endpoint():
    r = client.get("/v1/incidents")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_live_unknown_stop_404():
    r = client.get("/v1/bus-stops/ZZZZZZZZZZZZZZZZ")
    assert r.status_code == 404
    assert r.json()["code"] == "RESOURCE_NOT_FOUND"
