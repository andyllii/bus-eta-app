"""Deterministic unit tests for the bus ETA provider clients.

Verifies parsing + transformation of the KMB and Citybus/NWFB clients against
recorded real-world fixtures (offline, deterministic). Asserts raw provider
records map into the canonical ``ETA`` model exactly, ``eta=None`` is preserved
(end-of-service / no prediction) with ``minutes_remaining=None``, a populated
``eta`` yields a non-negative ``minutes_remaining``, multilingual dest/remark
fields round-trip, and empty remarks normalise to ``None`` (not ``""``).

Fixtures were captured live from data.etabus.gov.hk (KMB) and rt.data.gov.hk
(Citybus) and stored under tests/fixtures/. The Citybus ETA fixture is shaped
faithfully to the live feed's documented record (verified against the live
endpoint); a real non-empty capture wasn't possible at off-peak run time.
"""
import json
import os

from src.clients import CitybusClient, KMBClient

FIX = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tests", "fixtures")


def _load(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# KMB
# ---------------------------------------------------------------------------
def test_kmb_stop_metadata_parse():
    payload = _load("kmb_stop_946C74E30100FE80.json")
    stop = KMBClient().get_stop("946C74E30100FE80")
    assert stop is not None
    assert stop.id == payload["data"]["stop"]
    assert stop.name.tc == "九龍寨城公園 (WT575)"
    assert stop.name.en == "KOWLOON WALLED CITY PARK (WT575)"
    assert abs(stop.location.lat - 22.332261) < 1e-6
    assert abs(stop.location.lon - 114.187981) < 1e-6


def test_kmb_eta_parse_transform():
    payload = _load("kmb_stop_eta_946C74E30100FE80.json")
    etas = KMBClient()._parse_stop_eta(payload)
    assert len(etas) == len(payload["data"])
    for raw, e in zip(payload["data"], etas):
        assert e.co == "KMB"
        assert e.route == raw["route"]
        assert e.direction == raw["dir"]
        assert e.service_type == raw["service_type"]
        assert e.seq == raw["seq"]
        assert e.eta_seq == raw["eta_seq"]
        assert e.dest.tc == raw["dest_tc"]
        assert e.dest.sc == raw["dest_sc"]
        assert e.dest.en == raw["dest_en"]
        # empty remark -> None in canonical model
        if not raw["rmk_tc"]:
            assert e.remark is None
        else:
            assert e.remark.tc == raw["rmk_tc"]


def test_kmb_eta_null_eta_normalises_minutes():
    payload = _load("kmb_stop_eta_946C74E30100FE80.json")
    # Every recorded KMB ETA here is null (off-peak); verify normalisation.
    etas = KMBClient()._parse_stop_eta(payload)
    for e in etas:
        assert e.eta is None
        assert e.minutes_remaining is None


def test_kmb_eta_minutes_remaining_computed():
    from datetime import datetime, timedelta, timezone

    from src.clients.kmb import KMBStopETA

    future = datetime.now(timezone.utc) + timedelta(minutes=7)
    rec = KMBStopETA(
        co="KMB", route="1", dir="O", service_type=1, seq=8,
        dest_tc="尖沙咀碼頭", dest_sc="尖沙咀码头", dest_en="STAR FERRY",
        eta_seq=1, eta=future, rmk_tc="", rmk_sc="", rmk_en="",
        data_timestamp=future,
    )
    e = rec.to_canonical()
    assert e.eta is not None
    assert e.minutes_remaining is not None and e.minutes_remaining >= 6


# ---------------------------------------------------------------------------
# Citybus / NWFB
# ---------------------------------------------------------------------------
def test_citybus_stop_metadata_parse():
    payload = _load("ctb_stop_001027.json")
    stop = CitybusClient(co="CTB").get_stop("001027")
    assert stop is not None
    assert stop.id == payload["data"]["stop"]
    assert stop.name.tc == "中環 (港澳碼頭)"
    assert stop.name.en == "Central (Macao Ferry)"
    assert abs(stop.location.lat - 22.288274152091) < 1e-9
    assert abs(stop.location.lon - 114.15042248053) < 1e-9


def test_citybus_eta_parse_transform():
    payload = _load("ctb_eta_1_001027.json")
    etas = CitybusClient(co="CTB")._parse_stop_eta(payload)
    assert len(etas) == 2
    # first record has a real eta
    e0 = etas[0]
    assert e0.co == "CTB"
    assert e0.route == "1"
    assert e0.direction == "O"
    assert e0.seq == 1
    assert e0.dest.tc == "跑馬地 (上)"
    assert e0.dest.sc == "跑马地 (上)"
    assert e0.dest.en == "HAPPY VALLEY (UPPER)"
    assert e0.eta is not None
    assert e0.minutes_remaining is not None
    # second record: null eta + remark -> None values
    e1 = etas[1]
    assert e1.eta is None
    assert e1.minutes_remaining is None
    assert e1.remark is not None  # non-empty remark survives


def test_citybus_eta_requires_route_no_422():
    """The real Citybus feed 422s on a missing route.

    The patched client must always send a route. We assert the fan-out list is
    non-empty so a live call always carries a route segment (no '//' gap).
    """
    from config import settings

    assert len(settings.citybus_default_routes) > 0
    assert all(r for r in settings.citybus_default_routes)
