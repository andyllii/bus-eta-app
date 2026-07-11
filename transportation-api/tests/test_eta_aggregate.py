"""Offline unit tests for ``GET /api/v1/eta`` and its service.

These run with stub clients injected into :class:`EtaAggregateService`, so no
network is touched. They cover:

* happy path — ETAs + weather + incidents in one object, incidents ranked by
  relevance and sorted high-first;
* 404 when the stop/route is unknown (no ETA returned by any operator);
* 422 when a required query param is missing (FastAPI validation);
* ``include_weather=false`` / ``include_incidents=false`` toggles omit blocks;
* ``route`` filtering (only the requested route's ETAs are kept);
* fail-soft degradation — when weather raises, ``degraded=true`` and the rest
  of the payload is still returned (HTTP 200); with ``degrade=false`` the same
  failure becomes a 500;
* caching — the same request twice hits the service once (stub call counter);
* mock mode off the network.
"""
import datetime
from typing import List, Optional

import pytest
from fastapi.testclient import TestClient

from config import settings
from models import BusStop, ETA, GeoPoint, Incident, MultilingualText, Weather


# ---------------------------------------------------------------------------
# Stub clients
# ---------------------------------------------------------------------------
KMB_STOP = "946C74E30100FE80"


def _stub_eta(route="1", seq=12, minutes=4, eta=None):
    return ETA(
        co="KMB", route=route, direction="O", service_type=1, seq=seq,
        dest=MultilingualText(en="Central", tc="中環", sc="中环"),
        eta_seq=1,
        eta=eta or datetime.datetime(2026, 7, 10, 8, 49, 0, tzinfo=datetime.timezone.utc),
        minutes_remaining=minutes,
        remark=None,
        data_timestamp=datetime.datetime(2026, 7, 10, 8, 40, 0, tzinfo=datetime.timezone.utc),
    )


class StubKMB:
    provider = "kmb"

    def __init__(self, etas=None, stop=None, fail_get_stop=False):
        self._etas = etas if etas is not None else [ _stub_eta() ]
        self._stop = stop
        self._fail_get_stop = fail_get_stop
        self.eta_calls = 0

    def get_stop(self, stop_id):
        if self._fail_get_stop:
            raise RuntimeError("stop boom")
        if self._stop is None:
            return None
        return self._stop

    def get_stop_eta(self, stop_id, route=None):
        self.eta_calls += 1
        if self._stop is None:
            return []  # unknown stop -> no ETAs
        return list(self._etas)


class StubCitybus:
    provider = "citybus"

    def get_stop(self, stop_id):
        return None

    def get_stop_eta(self, stop_id, route=None):
        return []


class StubHKO:
    provider = "hko"

    def __init__(self, weather=None, fail=False):
        self._weather = weather
        self._fail = fail

    def get_current_weather(self):
        if self._fail:
            raise RuntimeError("hko boom")
        return self._weather


class StubTD:
    provider = "td"

    def __init__(self, incidents=None, fail=False):
        self._incidents = incidents if incidents is not None else []
        self._fail = fail

    def get_incidents(self):
        if self._fail:
            raise RuntimeError("td boom")
        return list(self._incidents)


def _service_with(stub_kmb, stub_hko, stub_td, cache_ttl=0.05):
    from src.services.eta_aggregate import EtaAggregateService

    return EtaAggregateService(
        lang="tc",
        cache_ttl=cache_ttl,
        kmb=stub_kmb,
        citybus=StubCitybus(),
        hko=stub_hko,
        td=stub_td,
    )


def _inc(rel, lat=22.333, lon=114.161, district=None, location=None):
    return Incident(
        id=f"TD-{rel}",
        heading=MultilingualText(tc="事故"),
        location=MultilingualText(tc=location or "道路"),
        district=MultilingualText(tc=district or "深水埗") if district else None,
        status=MultilingualText(tc="生效中"),
        relevance=rel,
        geo=GeoPoint(lat=lat, lon=lon),
    )


# ---------------------------------------------------------------------------
# Service-level tests
# ---------------------------------------------------------------------------
def test_service_happy_path_ranks_incidents():
    stop = BusStop(id=KMB_STOP, name=MultilingualText(tc="長沙灣廣場"),
                   location=GeoPoint(lat=22.333, lon=114.161))
    incs = [
        _inc("low", lat=22.40, lon=114.30),
        _inc("high", lat=22.333, lon=114.161),
        _inc("medium", lat=22.40, lon=114.30, location="長沙灣道路"),
    ]
    svc = _service_with(
        StubKMB(stop=stop),
        StubHKO(weather=Weather(description="Rain")),
        StubTD(incidents=incs),
    )
    agg = svc.get_eta_aggregate(route="1", stop_id=KMB_STOP)
    assert agg.query.route == "1"
    assert agg.query.stop_id == KMB_STOP
    assert agg.query.operator == "KMB"
    assert len(agg.etas) == 1
    assert agg.weather is not None
    # high -> medium -> low
    assert [i.relevance for i in agg.incidents] == ["high", "medium", "low"]
    assert agg.degraded is False


def test_service_unknown_stop_raises():
    from src.clients.exceptions import UpstreamError

    svc = _service_with(StubKMB(stop=None), StubHKO(), StubTD())
    with pytest.raises(UpstreamError):
        svc.get_eta_aggregate(route="1", stop_id=KMB_STOP)


def test_service_route_filter():
    stop = BusStop(id=KMB_STOP, name=MultilingualText(tc="x"),
                   location=GeoPoint(lat=0, lon=0))
    other = ETA(co="KMB", route="2", direction="O", service_type=1, seq=1,
                dest=MultilingualText(tc="y"), eta_seq=1,
                eta=datetime.datetime(2026, 7, 10, 9, 0, 0, tzinfo=datetime.timezone.utc),
                minutes_remaining=10)
    svc = _service_with(StubKMB(stop=stop, etas=[_stub_eta(), other]),
                        StubHKO(), StubTD())
    agg = svc.get_eta_aggregate(route="2", stop_id=KMB_STOP)
    assert [e.route for e in agg.etas] == ["2"]


def test_service_degrade_on_weather_failure():
    stop = BusStop(id=KMB_STOP, name=MultilingualText(tc="x"),
                   location=GeoPoint(lat=0, lon=0))
    svc = _service_with(StubKMB(stop=stop), StubHKO(fail=True), StubTD())
    # degrade=True (default) -> partial payload, degraded flag set
    agg = svc.get_eta_aggregate(route="1", stop_id=KMB_STOP, degrade=True)
    assert agg.weather is None
    assert agg.degraded is True
    assert len(agg.etas) == 1


def test_service_no_degrade_raises():
    from src.clients.exceptions import UpstreamError

    stop = BusStop(id=KMB_STOP, name=MultilingualText(tc="x"),
                   location=GeoPoint(lat=0, lon=0))
    svc = _service_with(StubKMB(stop=stop), StubHKO(fail=True), StubTD())
    with pytest.raises(UpstreamError):
        svc.get_eta_aggregate(route="1", stop_id=KMB_STOP, degrade=False)


def test_service_cache_hits_once():
    stop = BusStop(id=KMB_STOP, name=MultilingualText(tc="x"),
                   location=GeoPoint(lat=0, lon=0))
    kmb = StubKMB(stop=stop)
    svc = _service_with(kmb, StubHKO(), StubTD())
    svc.get_eta_aggregate(route="1", stop_id=KMB_STOP)
    svc.get_eta_aggregate(route="1", stop_id=KMB_STOP)
    # Second call served from cache -> upstream ETA fetched only once.
    assert kmb.eta_calls == 1


def test_service_mock_mode():
    settings.use_mock_data = True
    try:
        from src.services.eta_aggregate import EtaAggregateService

        svc = EtaAggregateService(lang="tc")
        agg = svc.get_eta_aggregate(route="1", stop_id=KMB_STOP)
        assert agg.query.operator == "KMB"
        assert any(e.route == "1" for e in agg.etas)
    finally:
        settings.use_mock_data = False


# ---------------------------------------------------------------------------
# Route-level tests
# ---------------------------------------------------------------------------
@pytest.fixture
def client(monkeypatch):
    """Inject stub clients into the route's service singleton."""
    from app import app
    from routes import eta_aggregate as mod

    stop = BusStop(id=KMB_STOP, name=MultilingualText(tc="長沙灣廣場"),
                   location=GeoPoint(lat=22.333, lon=114.161))
    incs = [
        _inc("low", lat=22.40, lon=114.30),
        _inc("high", lat=22.333, lon=114.161),
        _inc("medium", lat=22.40, lon=114.30, location="長沙灣道路"),
    ]
    svc = _service_with(StubKMB(stop=stop),
                        StubHKO(weather=Weather(description="Rain")),
                        StubTD(incidents=incs), cache_ttl=0)
    monkeypatch.setattr(mod, "_service", svc)
    return TestClient(app)


def test_route_happy(client):
    r = client.get(f"/api/v1/eta?route=1&stop={KMB_STOP}")
    assert r.status_code == 200
    data = r.json()
    assert data["query"]["route"] == "1"
    assert len(data["etas"]) == 1
    assert data["weather"] is not None
    assert [i["relevance"] for i in data["incidents"]] == ["high", "medium", "low"]
    assert data["degraded"] is False


def test_route_missing_param_422(client):
    r = client.get("/api/v1/eta?route=1")  # no stop
    assert r.status_code == 422


def test_route_unknown_404(client):
    from routes import eta_aggregate as mod

    # Unknown stop: stub returns no ETA.
    svc = _service_with(StubKMB(stop=None), StubHKO(), StubTD(), cache_ttl=0)
    mod._service = svc
    r = client.get(f"/api/v1/eta?route=1&stop={KMB_STOP}")
    assert r.status_code == 404
    assert r.json()["code"] == "RESOURCE_NOT_FOUND"


def test_route_toggles(client):
    r = client.get(f"/api/v1/eta?route=1&stop={KMB_STOP}&include_weather=false&include_incidents=false")
    assert r.status_code == 200
    data = r.json()
    assert data["weather"] is None
    assert data["incidents"] == []


def test_route_degrade_flag(client):
    from routes import eta_aggregate as mod

    stop = BusStop(id=KMB_STOP, name=MultilingualText(tc="x"),
                   location=GeoPoint(lat=0, lon=0))
    svc = _service_with(StubKMB(stop=stop), StubHKO(fail=True), StubTD(), cache_ttl=0)
    mod._service = svc
    r = client.get(f"/api/v1/eta?route=1&stop={KMB_STOP}")
    assert r.status_code == 200
    assert r.json()["degraded"] is True
    assert r.json()["weather"] is None


def test_route_openapi_present():
    from app import app

    paths = app.openapi()["paths"]
    assert "/api/v1/eta" in paths
    assert "get" in paths["/api/v1/eta"]
