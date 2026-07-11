#!/usr/bin/env python3
"""Record live KMB + Citybus samples to fixtures for deterministic parser tests.

Writes:
  tests/fixtures/kmb_stop_946C74E30100FE80.json
  tests/fixtures/kmb_stop_eta_946C74E30100FE80.json
  tests/fixtures/ctb_stop_001027.json        (always saved)
  tests/fixtures/ctb_eta_<route>_001027.json (first non-empty found)
"""
import json
import os
import urllib.request

UA = "transportation-api/0.2"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FX = os.path.join(ROOT, "tests", "fixtures")
os.makedirs(FX, exist_ok=True)


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8")


def save(name, text):
    with open(os.path.join(FX, name), "w", encoding="utf-8") as f:
        f.write(text)
    print("saved", name, len(text), "bytes")


# --- KMB ---
kmb_stop = get("https://data.etabus.gov.hk/v1/transport/kmb/stop/946C74E30100FE80")
save("kmb_stop_946C74E30100FE80.json", kmb_stop)

kmb_eta = get("https://data.etabus.gov.hk/v1/transport/kmb/stop-eta/946C74E30100FE80")
save("kmb_stop_eta_946C74E30100FE80.json", kmb_eta)

# --- Citybus stop ---
ctb_stop = get("https://rt.data.gov.hk/v2/transport/citybus/stop/001027")
save("ctb_stop_001027.json", ctb_stop)

# --- Citybus ETA: scan (route, stop) pairs for a non-empty sample ---
CTB_ROUTES = ["1", "6", "7", "71", "780", "M47", "12", "25", "90", "970",
              "A11", "A12", "E11", "N11", "N8", "973", "182", "681"]
STOPS = ["001027", "002546", "000123", "001739", "002133"]
found = False
for stop in STOPS:
    for route in CTB_ROUTES:
        try:
            text = get(f"https://rt.data.gov.hk/v2/transport/citybus/eta/CTB/{route}/{stop}")
        except Exception as e:
            continue
        try:
            obj = json.loads(text)
        except Exception:
            continue
        if obj.get("data"):
            save(f"ctb_eta_{route}_{stop}.json", text)
            print(f"  -> non-empty Citybus ETA at stop {stop} route {route} "
                  f"({len(obj['data'])} records)")
            found = True
            break
    if found:
        break
if not found:
    print("no non-empty Citybus ETA sample captured this run (off-peak); "
          "parser will rely on shape/unit tests instead")

print("done")
