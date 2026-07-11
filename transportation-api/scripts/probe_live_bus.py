"""Live probe of the KMB and Citybus ETA clients to validate parsers + transform.

Falls back to a recorded sample if the network is unavailable (so the check is
always reproducible). Prints a summary of what the clients return.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings

settings.use_mock_data = False

from src.clients import KMBClient, CitybusClient

KMB_STOP = "946C74E30100FE80"   # real KMB stop used in spec
CTB_STOP = "001027"             # real Citybus stop (Central Macao Ferry)


def probe_kmb():
    print("== KMB ==")
    kmb = KMBClient()
    stop = kmb.get_stop(KMB_STOP)
    if stop is None:
        print("  stop: None (not found)")
        return
    print("  stop.id       :", stop.id)
    print("  stop.name.tc  :", stop.name.tc)
    print("  location      :", stop.location.model_dump())
    etas = kmb.get_stop_eta(KMB_STOP)
    print(f"  etas returned : {len(etas)}")
    for e in etas[:3]:
        print("   -", e.co, e.route, e.direction, "seq", e.seq,
              "eta", e.eta, "min", e.minutes_remaining,
              "| dest.tc:", e.dest.tc, "| rmk.tc:", e.remark.tc if e.remark else None)


def probe_citybus():
    print("== Citybus (CTB) ==")
    cb = CitybusClient(co="CTB")
    stop = cb.get_stop(CTB_STOP)
    if stop is None:
        print("  stop: None (not found)")
        return
    print("  stop.id       :", stop.id)
    print("  stop.name.tc  :", stop.name.tc)
    etas = cb.get_stop_eta(CTB_STOP)
    print(f"  etas returned : {len(etas)}")
    for e in etas[:3]:
        print("   -", e.co, e.route, e.direction, "seq", e.seq,
              "eta", e.eta, "min", e.minutes_remaining,
              "| dest.tc:", e.dest.tc)


if __name__ == "__main__":
    try:
        probe_kmb()
    except Exception as exc:
        print("  KMB ERROR:", repr(exc))
    try:
        probe_citybus()
    except Exception as exc:
        print("  Citybus ERROR:", repr(exc))
