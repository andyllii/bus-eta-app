"""Full-stack live smoke test of GET /api/v1/weather/hk (no mocking).

Exercises route -> WeatherApiService -> HKOClient -> live HKO, then confirms
the endpoint-level 10-min cache actually shields HKO (second call must NOT
hit the network again). We detect network reuse by counting outbound requests.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from fastapi.testclient import TestClient

from app import app
from src.clients.hko import HKOClient

_real_get = requests.get
_calls = {"n": 0}


def _counting_get(*args, **kwargs):
    _calls["n"] += 1
    return _real_get(*args, **kwargs)


def main() -> int:
    requests.get = _counting_get
    client = TestClient(app)

    r1 = client.get("/api/v1/weather/hk?lang=en")
    assert r1.status_code == 200, r1.status_code
    d1 = r1.json()
    assert d1["temperature"]["value"] is not None
    assert d1["description"]
    first_calls = _calls["n"]
    print(f"first request -> HTTP {r1.status_code}, HKO calls: {first_calls}")
    print("  temp:", d1["temperature"], "| desc:", d1["description"],
          "| warnings:", len(d1["warnings"]))

    r2 = client.get("/api/v1/weather/hk?lang=en")
    assert r2.status_code == 200
    second_calls = _calls["n"]
    print(f"second request (same variant) -> HKO calls: {second_calls}")
    # The endpoint cache must serve the repeat without touching HKO again.
    assert second_calls == first_calls, (
        f"cache did not shield HKO: calls went {first_calls} -> {second_calls}"
    )

    r3 = client.get("/api/v1/weather/hk/warnings?lang=tc")
    assert r3.status_code == 200
    print("warnings subroute -> HTTP", r3.status_code,
          "| count:", len(r3.json()))

    print("\nFULL-STACK LIVE SMOKE PASSED (cache shielded HKO on repeat)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
