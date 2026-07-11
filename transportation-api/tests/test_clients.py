"""Unit tests for the provider transformer / client logic (offline).

These cover the parse-and-transform path of each client WITHOUT hitting the
network: raw provider payloads are fed in directly (mirroring the shapes we
observed on the live feeds) and we assert the canonical models come out
correct, including edge cases (null eta, empty remarks, unknown stop, malformed
records, missing warnings).
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from models import BusStop, ETA, Weather, WeatherWarning, Incident, MultilingualText
from src.clients import KMBClient, CitybusClient, HKOClient, TDClient


# --- KMB ----------------------------------------------------------------------
def test_kmb_stop_eta_transform():
    payload = {
        "type": "StopETA", "version": "1.0",
        "generated_timestamp": "2026-07-11T02:56:31+08:00",
        "data": [
            {"co": "KMB", "route": "1", "dir": "O", "service_type": 1, "seq": 8,
             "dest_tc": "尖沙咀碼頭", "dest_sc": "尖沙咀码头", "dest_en": "STAR FERRY",
             "eta_seq": 1, "eta": None, "rmk_tc": "", "rmk_sc": "", "rmk_en": "",
             "data_timestamp": "2026-07-11T02:56:08+08:00"},
            {"co": "KMB", "route": "1", "dir": "O", "service_type": 1, "seq": 8,
             "dest_tc": "尖沙咀碼頭", "dest_sc": "尖沙咀码头", "dest_en": "STAR FERRY",
             "eta_seq": 2, "eta": "2026-07-11T03:10:00+08:00",
             "rmk_tc": "預定", "rmk_sc": "预定", "rmk_en": "Scheduled",
             "data_timestamp": "2026-07-11T02:56:08+08:00"},
        ],
    }
    client = KMBClient()
    # bypass HTTP by calling the parser directly via _get_json monkeypatch
    client._get_json = lambda *a, **k: payload  # type: ignore[assignment]
    etas = client.get_stop_eta("946C74E30100FE80")
    assert len(etas) == 2
    e0, e1 = etas
    assert e0.co == "KMB" and e0.route == "1" and e0.direction == "O"
    assert e0.eta is None and e0.minutes_remaining is None
    assert e0.remark is None or e0.remark.tc is None  # empty remarks normalised to None
    assert e1.eta is not None
    assert e1.minutes_remaining is not None and e1.minutes_remaining >= 0
    assert e1.dest.en == "STAR FERRY"
    assert e1.remark.tc == "預定"


def test_kmb_stop_metadata_transform():
    payload = {"type": "Stop", "version": "1.0",
               "generated_timestamp": "2026-07-11T02:56:31+08:00",
               "data": {"stop": "946C74E30100FE80", "name_en": "KOWLOON WALLED CITY PARK",
                        "name_tc": "九龍寨城公園", "name_sc": "九龙寨城公园",
                        "lat": "22.332261", "long": "114.187981"}}
    client = KMBClient()
    client._get_json = lambda *a, **k: payload  # type: ignore[assignment]
    stop = client.get_stop("946C74E30100FE80")
    assert isinstance(stop, BusStop)
    assert stop.id == "946C74E30100FE80"
    assert stop.location.lat == pytest.approx(22.332261)
    assert stop.location.lon == pytest.approx(114.187981)
    assert stop.name.tc == "九龍寨城公園"


def test_kmb_unknown_stop_returns_none():
    payload = {"type": "Stop", "version": "1.0", "generated_timestamp": "x", "data": {}}
    client = KMBClient()
    client._get_json = lambda *a, **k: payload  # type: ignore[assignment]
    assert client.get_stop("DEADBEEF") is None
    assert client.get_stop_eta("DEADBEEF") == []


def test_kmb_skips_malformed_record():
    payload = {"type": "StopETA", "version": "1.0", "generated_timestamp": "2026-07-11T02:56:31+08:00",
               "data": [{"co": "KMB"}, {"co": "KMB", "route": "1", "dir": "O", "service_type": 1,
                        "seq": 8, "dest_tc": "尖沙咀", "dest_sc": "尖沙咀", "dest_en": "TST",
                        "eta_seq": 1, "eta": None, "rmk_tc": "", "rmk_sc": "", "rmk_en": "",
                        "data_timestamp": "2026-07-11T02:56:08+08:00"}]}
    client = KMBClient()
    client._get_json = lambda *a, **k: payload  # type: ignore[assignment]
    etas = client.get_stop_eta("X")
    assert len(etas) == 1


# --- Citybus -----------------------------------------------------------------
def test_citybus_stop_transform():
    stop_payload = {"type": "Stop", "version": "2.0", "generated_timestamp": "x",
                    "data": {"stop": "001027", "name_tc": "中環 (港澳碼頭)",
                             "name_en": "Central (Macao Ferry)", "name_sc": "中环 (港澳码头)",
                             "lat": "22.288274152091", "long": "114.15042248053"}}
    client = CitybusClient(co="CTB")
    client._get_json = lambda *a, **k: stop_payload  # type: ignore[assignment]
    stop = client.get_stop("001027")
    assert stop.id == "001027"
    assert stop.location.lat == pytest.approx(22.28827, rel=1e-4)


def test_citybus_eta_transform():
    payload = {"type": "ETA", "version": "2.0", "generated_timestamp": "2026-07-11T02:59:02+08:00",
               "data": [{"co": "CTB", "route": "1", "dir": "O", "seq": 1, "stop": "001027",
                         "dest_tc": "跑馬地 (上)", "dest_sc": "跑马地 (上)", "dest_en": "Happy Valley (Upper)",
                         "eta_seq": 1, "eta": "2026-07-11T03:01:02+08:00",
                         "rmk_tc": "", "rmk_sc": "", "rmk_en": "", "data_timestamp": "2026-07-11T02:59:02+08:00"}]}
    client = CitybusClient(co="CTB")
    client._get_json = lambda *a, **k: payload  # type: ignore[assignment]
    etas = client.get_stop_eta("001027", route="1")
    assert len(etas) == 1
    assert etas[0].co == "CTB" and etas[0].route == "1"


# --- HKO ---------------------------------------------------------------------
def test_hko_weather_transform():
    rhr = {"temperature": {"data": [{"place": "香港天文台", "value": 29, "unit": "C"}]},
           "humidity": {"recordTime": "2026-07-11T02:00:00+08:00",
                        "data": [{"unit": "percent", "value": 81, "place": "香港天文台"}]},
           "icon": [75], "iconUpdateTime": "2026-07-11T01:45:00+08:00",
           "updateTime": "2026-07-11T02:02:00+08:00",
           "warningMessage": ["酷熱天氣警告現正生效。"]}
    warnsum = {"WHOT": {"name": "Very Hot Weather Warning", "code": "WHOT",
                        "issueTime": "2026-07-10T11:30:00+08:00",
                        "updateTime": "2026-07-10T16:20:00+08:00"}}
    warninginfo = {"details": [{"contents": ["The Very Hot Weather Warning is now in force."],
                                "warningStatementCode": "WHOT",
                                "updateTime": "2026-07-10T16:20:00+08:00"}]}
    client = HKOClient(lang="en")
    payloads = {"rhrread": rhr, "warnsum": warnsum, "warningInfo": warninginfo}
    client._get_json = lambda url, params=None: payloads.get(params["dataType"])  # type: ignore[assignment]
    weather = client.get_current_weather()
    assert isinstance(weather, Weather)
    assert weather.temperature["value"] == 29
    assert weather.humidity["value"] == 81
    assert weather.icon == [75]
    assert len(weather.warnings) == 1
    w = weather.warnings[0]
    assert w.code == "WHOT"
    assert w.severity == "warning"
    # Title is multilingual via the static map (tc/sc always populated).
    assert w.title.en == "Very Hot Weather Warning"
    assert w.title.tc == "酷熱天氣警告"


def test_hko_no_warnings():
    rhr = {"temperature": {"data": []}, "humidity": {"recordTime": "x", "data": []},
           "icon": [61], "updateTime": "2026-07-11T02:00:00+08:00", "warningMessage": []}
    client = HKOClient()
    payloads = {"rhrread": rhr, "warnsum": {}, "warningInfo": {"details": []}}
    client._get_json = lambda url, params=None: payloads.get(params["dataType"])  # type: ignore[assignment]
    weather = client.get_current_weather()
    assert weather is not None
    assert weather.warnings == []


# --- TD ----------------------------------------------------------------------
def test_td_incident_transform():
    import xml.etree.ElementTree as ET
    xml = (
        '<list><message>'
        '<INCIDENT_NUMBER>TD20260710-00123</INCIDENT_NUMBER>'
        '<INCIDENT_HEADING_EN>Road blocked due to accident</INCIDENT_HEADING_EN>'
        '<INCIDENT_HEADING_CN>因交通意外道路封閉</INCIDENT_HEADING_CN>'
        '<INCIDENT_DETAIL_EN>One lane closed</INCIDENT_DETAIL_EN>'
        '<INCIDENT_DETAIL_CN>一條行車線封閉</INCIDENT_DETAIL_CN>'
        '<LOCATION_EN>Cheung Sha Wan Road</LOCATION_EN>'
        '<LOCATION_CN>長沙灣道</LOCATION_CN>'
        '<DISTRICT_EN>Sham Shui Po</DISTRICT_EN>'
        '<INCIDENT_STATUS_EN>ACTIVE</INCIDENT_STATUS_EN>'
        '<INCIDENT_STATUS_CN>生效中</INCIDENT_STATUS_CN>'
        '<ANNOUNCEMENT_DATE>2026-07-10 08:30</ANNOUNCEMENT_DATE>'
        '<ROAD_TYPE_EN>Road</ROAD_TYPE_EN>'
        '<ROAD_TYPE_CN>道路</ROAD_TYPE_CN>'
        '</message></list>'
    )
    client = TDClient(lang="tc")
    client._get_text = lambda *a, **k: xml  # type: ignore[assignment]
    incidents = client.get_incidents()
    assert len(incidents) == 1
    inc = incidents[0]
    assert isinstance(inc, Incident)
    assert inc.id == "TD20260710-00123"
    assert inc.heading.tc == "因交通意外道路封閉"
    assert inc.status.tc == "生效中"
    assert inc.district.en == "Sham Shui Po"


def test_td_empty_feed():
    client = TDClient(lang="tc")
    client._get_text = lambda *a, **k: "<list></list>"  # type: ignore[assignment]
    assert client.get_incidents() == []
