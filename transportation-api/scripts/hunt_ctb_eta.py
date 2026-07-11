#!/usr/bin/env python3
"""Hunt for a non-empty Citybus ETA sample (off-peak: try night routes)."""
import json
import os
import urllib.request

UA = "transportation-api/0.2"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FX = os.path.join(ROOT, "tests", "fixtures")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8")


# night / 24h routes + several busy stops
ROUTES = ["N11", "N8", "N8P", "N8X", "N90", "N170", "N182", "N21", "N23",
          "N29", "N118", "NA11", "A11", "A12", "A21", "E11", "E21", "N973"]
STOPS = ["001739", "002133", "000123", "002546", "002855", "003176",
         "000389", "001027", "001324"]

for stop in STOPS:
    for route in ROUTES:
        try:
            text = get(f"https://rt.data.gov.hk/v2/transport/citybus/eta/CTB/{route}/{stop}")
        except Exception:
            continue
        try:
            obj = json.loads(text)
        except Exception:
            continue
        if obj.get("data"):
            path = os.path.join(FX, f"ctb_eta_{route}_{stop}.json")
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            print(f"FOUND non-empty Citybus ETA: stop {stop} route {route} "
                  f"({len(obj['data'])} records) -> {path}")
            # show first record shape
            print("  sample record:", json.dumps(obj["data"][0], ensure_ascii=False))
            raise SystemExit(0)
print("still no non-empty Citybus ETA sample (off-peak night service)")
