"""Validate the patched Citybus client live: no 422, valid URL always."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings

settings.use_mock_data = False

from src.clients import CitybusClient, KMBClient

CTB_STOP = "001027"

print("== Citybus: no-route fan-out (should NOT 422) ==")
cb = CitybusClient(co="CTB")
try:
    etas = cb.get_stop_eta(CTB_STOP)
    print(f"  ok, {len(etas)} etas (likely 0 at this off-peak hour)")
except Exception as exc:
    print("  ERROR:", repr(exc))

print("== Citybus: explicit route (1) ==")
try:
    etas = cb.get_stop_eta(CTB_STOP, route="1")
    print(f"  ok, {len(etas)} etas")
except Exception as exc:
    print("  ERROR:", repr(exc))

print("== KMB regression check ==")
kmb = KMBClient()
try:
    stop = kmb.get_stop("946C74E30100FE80")
    etas = kmb.get_stop_eta("946C74E30100FE80")
    print(f"  stop={stop.id}, etas={len(etas)} (regression clean)")
except Exception as exc:
    print("  ERROR:", repr(exc))
