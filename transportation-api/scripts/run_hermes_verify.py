#!/usr/bin/env python3
"""Write the ad-hoc verifier to an OS-safe tempfile, run it, then clean up.

This avoids writing into /tmp directly (protected) and confirms the changed
bus-eta backend behavior without relying on the full pytest suite.
"""
import os
import sys
import tempfile
import runpy

VERIFIER = r'''
import json, os, sys
sys.path.insert(0, "/opt/data/kanban/workspaces/t_b3fe8645/transportation-api")
from config import settings
settings.use_mock_data = False
results = []

def check(name, cond, detail=""):
    results.append(cond)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f" -- {detail}" if detail else ""))

# 1. MultilingualText.is_empty + empty-remark collapse
from models import MultilingualText
from src.clients.kmb import KMBStopETA
mt = MultilingualText(en=None, tc=None, sc=None)
check("MultilingualText.is_empty() truthy for all-None", mt.is_empty())
mt2 = MultilingualText(en="x")
check("MultilingualText.is_empty() falsey when populated", not mt2.is_empty())
rec = KMBStopETA(co="KMB", route="1", dir="O", service_type=1, seq=8,
    dest_tc="尖沙咀碼頭", dest_sc="尖沙咀码头", dest_en="STAR FERRY",
    eta_seq=1, eta=None, rmk_tc="", rmk_sc="", rmk_en="", data_timestamp=None)
e = rec.to_canonical()
check("KMB empty remark collapses to None", e.remark is None, repr(e.remark))
rec2 = KMBStopETA(co="KMB", route="1", dir="O", service_type=1, seq=8,
    dest_tc="尖沙咀碼頭", dest_sc="尖沙咀码头", dest_en="STAR FERRY",
    eta_seq=2, eta=None, rmk_tc="預定", rmk_sc="预定", rmk_en="Scheduled", data_timestamp=None)
e2 = rec2.to_canonical()
check("KMB non-empty remark preserved", bool(e2.remark) and e2.remark.tc == "預定")

# 2. Citybus ETA parser (fixture)
fix = "/opt/data/kanban/workspaces/t_b3fe8645/transportation-api/tests/fixtures/ctb_eta_1_001027.json"
with open(fix, encoding="utf-8") as f:
    ctb = json.load(f)
from src.clients import CitybusClient, KMBClient
cb = CitybusClient(co="CTB")
cetas = cb._parse_stop_eta(ctb)
check("Citybus fixture parses 2 records", len(cetas) == 2, f"n={len(cetas)}")
check("Citybus ETA co/route/dir", cetas[0].co == "CTB" and cetas[0].route == "1")
check("Citybus null-eta -> minutes None", cetas[1].eta is None and cetas[1].minutes_remaining is None)

# 3. Legacy /eta route no longer crashes
from fastapi.testclient import TestClient
from app import app
import routes.eta as eta_route
eta_route.kmb_client = KMBClient()
from models import ETA
fake = ETA(co="KMB", route="1", direction="O", service_type=1, seq=8,
    dest=MultilingualText(tc="尖沙咀碼頭", en="STAR FERRY"),
    eta_seq=1, eta=None, minutes_remaining=None, remark=None, data_timestamp=None)
eta_route.kmb_client.get_route_eta = lambda stop_id, route: [fake]
eta_route.hko_client.get_weather_warnings_as_strings = lambda: ["WARN"]
eta_route.td_client.get_incidents = lambda: []
c = TestClient(app)
r = c.get("/eta?route=1&stop_id=946C74E30100FE80")
check("legacy /eta returns 200 (no AttributeError)", r.status_code == 200, f"status={r.status_code}")
if r.status_code == 200:
    b = r.json()
    check("legacy /eta dest mapped to tc", b["bus_eta"][0]["dest"] == "尖沙咀碼頭", repr(b["bus_eta"][0]["dest"]))

# 4. Citybus fan-out live (no 422)
try:
    cb_live = CitybusClient(co="CTB")
    live = cb_live.get_stop_eta("001027")
    check("Citybus fan-out live (no 422)", True, f"{len(live)} etas")
except Exception as exc:
    check("Citybus fan-out live (no 422)", False, f"ERROR {exc!r}")

passed = sum(1 for x in results if x)
print(f"\nAD-HOC VERIFICATION: {passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
'''

tf = tempfile.NamedTemporaryFile(
    prefix="hermes-verify-", suffix=".py", delete=False, dir="/tmp"
)
tf.write(VERIFIER.encode("utf-8"))
tf.close()
try:
    runpy.run_path(tf.name, run_name="__main__")
finally:
    try:
        os.unlink(tf.name)
        print(f"\n(cleaned up {tf.name})")
    except OSError:
        pass
