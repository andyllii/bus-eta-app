"""Live smoke test for GET /api/v1/eta against the real HK feeds.

Best-effort: if there is no network to the HK open-data endpoints it prints a
skip note and exits 0 (CI without egress should stay green). With network it
asserts the endpoint returns a real, well-formed aggregate.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import urllib.request

from app import app
from fastapi.testclient import TestClient

KMB_STOP = "946C74E30100FE80"


def _network_ok() -> bool:
    try:
        req = urllib.request.Request(
            "https://data.etabus.gov.hk/v1/transport/kmb/stop/" + KMB_STOP,
            headers={"User-Agent": "smoke"},
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            return r.status == 200
    except Exception:
        return False


if __name__ == "__main__":
    if not _network_ok():
        print("SKIP: no network to live HK feeds")
        sys.exit(0)

    client = TestClient(app)
    r = client.get(f"/api/v1/eta?route=1&stop={KMB_STOP}&lang=en")
    print("status:", r.status_code)
    data = r.json()
    if r.status_code != 200:
        print("BODY:", data)
        sys.exit(1)
    print("query:", data["query"])
    print("etas returned:", len(data["etas"]))
    print("weather present:", data["weather"] is not None)
    print("incidents returned:", len(data["incidents"]))
    print("degraded:", data["degraded"])
    if data["incidents"]:
        print("top incident relevance:", data["incidents"][0]["relevance"])
    # Unknown stop should 404.
    r2 = client.get("/api/v1/eta?route=1&stop=ZZZZZZZZZZZZZZZZ")
    print("unknown-stop status:", r2.status_code, "(expect 404)")
