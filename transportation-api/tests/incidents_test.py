"""Tests for the Transport Department road-incident endpoint (/v1/incidents).

Network-free: the endpoint test monkeypatches ``TDClient.get_incidents`` so no
live HTTP call is made. XML parsing is exercised by injecting a sample feed
into ``TDClient._get_text``. (The combined /v1/bus-stops endpoint and the live
TD feed are covered in test_clients.py and test_backend_integration.py.)
"""
import os
import sys

import pytest
from fastapi.testclient import TestClient

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import app  # noqa: E402
from src.clients import TDClient  # noqa: E402
from src.services import IncidentService  # noqa: E402
from models import BusStop, GeoPoint, Incident, MultilingualText  # noqa: E402

client = TestClient(app)

SAMPLE_XML = """<list><message>
<INCIDENT_NUMBER>TD20260710-00123</INCIDENT_NUMBER>
<INCIDENT_HEADING_EN>Road blocked due to accident</INCIDENT_HEADING_EN>
<INCIDENT_HEADING_CN>因交通意外道路封閉</INCIDENT_HEADING_CN>
<INCIDENT_DETAIL_EN>One lane closed</INCIDENT_DETAIL_EN>
<INCIDENT_DETAIL_CN>一條行車線封閉</INCIDENT_DETAIL_CN>
<LOCATION_EN>Cheung Sha Wan Road</LOCATION_EN>
<LOCATION_CN>長沙灣道</LOCATION_CN>
<DISTRICT_EN>Sham Shui Po</DISTRICT_EN>
<INCIDENT_STATUS_EN>ACTIVE</INCIDENT_STATUS_EN>
<INCIDENT_STATUS_CN>生效中</INCIDENT_STATUS_CN>
<ANNOUNCEMENT_DATE>2026-07-10 08:30</ANNOUNCEMENT_DATE>
<ROAD_TYPE_EN>Road</ROAD_TYPE_EN>
<ROAD_TYPE_CN>道路</ROAD_TYPE_CN>
</message></list>"""


def test_parse_sample_xml():
    client_td = TDClient(lang="tc")
    client_td._get_text = lambda *a, **k: SAMPLE_XML  # type: ignore[assignment]
    incidents = client_td.get_incidents()
    assert len(incidents) >= 1
    inc = incidents[0]
    assert isinstance(inc, Incident)
    assert inc.id == "TD20260710-00123"
    assert inc.heading.en == "Road blocked due to accident"
    assert inc.heading.tc == "因交通意外道路封閉"
    assert inc.location.tc == "長沙灣道"
    assert inc.district.en == "Sham Shui Po"


def test_parse_handles_empty():
    client_td = TDClient(lang="tc")
    client_td._get_text = lambda *a, **k: "<list></list>"  # type: ignore[assignment]
    assert client_td.get_incidents() == []


def test_endpoint_returns_models(monkeypatch):
    sample = Incident(
        id="TD20260710-00123",
        heading=MultilingualText(en="Road blocked", tc="道路封閉"),
        location=MultilingualText(en="Cheung Sha Wan Road", tc="長沙灣道"),
        status=MultilingualText(en="ACTIVE", tc="生效中"),
        announcement_date="2026-07-10 08:30",
        relevance="high",
    )

    def fake(self):
        return [sample]

    monkeypatch.setattr(TDClient, "get_incidents", fake)
    # Canonical spec path.
    r = client.get("/api/v1/incidents")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    assert data[0]["id"] == "TD20260710-00123"
    assert data[0]["heading"]["en"] == "Road blocked"
    # Deprecated alias must still work.
    r_legacy = client.get("/v1/incidents")
    assert r_legacy.status_code == 200
    assert r_legacy.json()[0]["id"] == "TD20260710-00123"


def test_endpoint_failure_returns_500_envelope(monkeypatch):
    def boom(self):
        raise RuntimeError("network down")

    monkeypatch.setattr(TDClient, "get_incidents", boom)
    r = client.get("/api/v1/incidents")
    # TD errors are surfaced as a 500 Error envelope (not silently empty).
    assert r.status_code == 500
    assert r.json()["code"] == "UPSTREAM_ERROR"


def test_openapi_includes_incidents_route():
    spec = app.openapi()
    assert "/api/v1/incidents" in spec["paths"]
    assert "get" in spec["paths"]["/api/v1/incidents"]
    # Deprecated alias also present.
    assert "/v1/incidents" in spec["paths"]


# --- Rich-feed parsing: ID / CONTENT / LATITUDE / LONGITUDE / date ----------
RICH_XML = """<list><message>
<INCIDENT_NUMBER>IN-26-04927</INCIDENT_NUMBER>
<INCIDENT_HEADING_EN>Road Incident</INCIDENT_HEADING_EN>
<INCIDENT_HEADING_CN>道路事故</INCIDENT_HEADING_CN>
<INCIDENT_DETAIL_EN>Traffic Accident</INCIDENT_DETAIL_EN>
<INCIDENT_DETAIL_CN>交通意外</INCIDENT_DETAIL_CN>
<LOCATION_EN>Hiram's Highway</LOCATION_EN>
<LOCATION_CN>西貢公路</LOCATION_CN>
<DISTRICT_EN>Sai Kung</DISTRICT_EN>
<DISTRICT_CN>西貢</DISTRICT_CN>
<INCIDENT_STATUS_EN>NEW</INCIDENT_STATUS_EN>
<INCIDENT_STATUS_CN>最新情況</INCIDENT_STATUS_CN>
<ANNOUNCEMENT_DATE>2026-07-11T10:21:00</ANNOUNCEMENT_DATE>
<NEAR_LANDMARK_EN>Chui Tong Road</NEAR_LANDMARK_EN>
<NEAR_LANDMARK_CN>翠塘路</NEAR_LANDMARK_CN>
<ID>141824</ID>
<CONTENT_EN>part of the lanes is closed</CONTENT_EN>
<CONTENT_CN>部份行車線封閉</CONTENT_CN>
<LATITUDE>22.339</LATITUDE>
<LONGITUDE>114.274</LONGITUDE>
</message></list>"""


def test_parse_rich_feed_maps_all_fields():
    client_td = TDClient(lang="tc")
    client_td._get_text = lambda *a, **k: RICH_XML  # type: ignore[assignment]
    inc = client_td.get_incidents()[0]
    # Fields previously dropped by the client must now populate.
    assert inc.source_id == "141824"
    assert inc.content is not None and inc.content.en == "part of the lanes is closed"
    assert inc.geo is not None
    assert abs(inc.geo.lat - 22.339) < 1e-6
    assert abs(inc.geo.lon - 114.274) < 1e-6
    # ISO-8601 announcement date normalised to "YYYY-MM-DD HH:MM".
    assert inc.announcement_date == "2026-07-11 10:21"
    assert inc.id == "IN-26-04927"
    assert inc.district.en == "Sai Kung"
    assert inc.status.en == "NEW"


def test_parse_handles_empty_geo_and_date():
    client_td = TDClient(lang="tc")
    client_td._get_text = lambda *a, **k: "<list></list>"  # type: ignore[assignment]
    assert client_td.get_incidents() == []


def test_endpoint_supports_district_filter(monkeypatch):
    sample = Incident(
        id="IN-26-04927",
        heading=MultilingualText(en="Road Incident", tc="道路事故"),
        location=MultilingualText(en="Hiram's Highway", tc="西貢公路"),
        district=MultilingualText(en="Sai Kung", tc="西貢"),
        status=MultilingualText(en="NEW", tc="最新情況"),
        announcement_date="2026-07-11 10:21",
    )

    def fake(self, district=None, status=None):
        return [sample]

    monkeypatch.setattr(IncidentService, "get_incidents", fake)
    r = client.get("/api/v1/incidents?district=sai%20kung")
    assert r.status_code == 200
    data = r.json()
    assert data[0]["district"]["en"] == "Sai Kung"


# --- Relevance correlation --------------------------------------------------
def _incident(**kw) -> Incident:
    kw.setdefault("id", "TD-TEST-1")
    kw.setdefault("heading", MultilingualText(en="x"))
    kw.setdefault("location", MultilingualText(en="Somewhere"))
    kw.setdefault("status", MultilingualText(en="ACTIVE"))
    return Incident(**kw)


def test_correlate_geo_high():
    from src.services.incidents import IncidentService

    stop = BusStop(
        id="S1",
        name=MultilingualText(en="Nearby Stop"),
        location=GeoPoint(lat=22.339, lon=114.274),
        routes=["1"],
    )
    inc = _incident(geo=GeoPoint(lat=22.3395, lon=114.2745))
    svc = IncidentService(td=TDClient(lang="tc"))
    out = svc.correlate_for_stop(stop, incidents=[inc])
    assert out[0].relevance == "high"


def test_correlate_district_medium():
    from src.services.incidents import IncidentService

    stop = BusStop(
        id="S2",
        name=MultilingualText(en="Sai Kung Plaza", tc="西貢廣場"),
        location=GeoPoint(lat=22.30, lon=114.20),
        routes=["1"],
    )
    inc = _incident(district=MultilingualText(en="Sai Kung", tc="西貢"))
    svc = IncidentService(td=TDClient(lang="tc"))
    out = svc.correlate_for_stop(stop, incidents=[inc])
    assert out[0].relevance == "medium"


def test_correlate_no_match_low():
    from src.services.incidents import IncidentService

    stop = BusStop(
        id="S3",
        name=MultilingualText(en="Central Stop"),
        location=GeoPoint(lat=22.28, lon=114.16),
        routes=["1"],
    )
    inc = _incident(location=MultilingualText(en="Tuen Mun Road", tc="屯門公路"))
    svc = IncidentService(td=TDClient(lang="tc"))
    out = svc.correlate_for_stop(stop, incidents=[inc])
    assert out[0].relevance == "low"


def test_correlate_sorts_high_first():
    from src.services.incidents import IncidentService

    stop = BusStop(
        id="S4",
        name=MultilingualText(en="Stop"),
        location=GeoPoint(lat=22.339, lon=114.274),
        routes=["1"],
    )
    near = _incident(id="near", geo=GeoPoint(lat=22.3395, lon=114.2745))
    far = _incident(id="far", location=MultilingualText(en="Tuen Mun Road"))
    svc = IncidentService(td=TDClient(lang="tc"))
    out = svc.correlate_for_stop(stop, incidents=[far, near])
    assert out[0].id == "near"
    assert out[0].relevance == "high"

