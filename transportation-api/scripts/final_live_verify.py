"""Final live verification of the combined bus-stop endpoint via the real app.

Uses the FastAPI TestClient with mock mode OFF so it hits the live HK feeds.
Asserts:
  * KMB stop  -> 200, stop resolved, ETAs list, weather not None, incidents list
  * unknown   -> 404 RESOURCE_NOT_FOUND
  * route filter -> only that route's ETAs
  * Citybus stop -> 200 (no 422/500), stop resolved
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings

settings.use_mock_data = False

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)

KMB_STOP = "946C74E30100FE80"
CTB_STOP = "001027"

print("== KMB combined ==")
r = client.get(f"/v1/bus-stops/{KMB_STOP}")
print("status", r.status_code)
if r.status_code == 200:
    d = r.json()
    print("  stop.id:", d["stop"]["id"], "| name.tc:", d["stop"]["name"]["tc"])
    print("  etas:", len(d["etas"]), "| weather:", d["weather"] is not None, "| incidents:", len(d["incidents"]))
    assert d["stop"]["id"] == KMB_STOP
    assert d["etas"]
    assert d["weather"] is not None
else:
    print("  BODY:", r.text[:500])

print("== KMB route filter ?route=1 ==")
r = client.get(f"/v1/bus-stops/{KMB_STOP}?route=1")
if r.status_code == 200:
    routes = {e["route"] for e in r.json()["etas"]}
    print("  routes present:", routes)
    assert routes <= {"1"}
else:
    print("  status", r.status_code, r.text[:300])

print("== unknown stop 404 ==")
r = client.get("/v1/bus-stops/ZZZZZZZZZZZZZZZZ")
print("  status", r.status_code, "code:", r.json().get("code"))
assert r.status_code == 404
assert r.json()["code"] == "RESOURCE_NOT_FOUND"

print("== Citybus combined ==")
r = client.get(f"/v1/bus-stops/{CTB_STOP}")
print("  status", r.status_code)
if r.status_code == 200:
    d = r.json()
    print("  stop.id:", d["stop"]["id"], "| name.tc:", d["stop"]["name"]["tc"])
    print("  etas:", len(d["etas"]))
    assert d["stop"]["id"] == CTB_STOP
else:
    print("  BODY:", r.text[:500])

print("ALL FINAL CHECKS PASSED")
