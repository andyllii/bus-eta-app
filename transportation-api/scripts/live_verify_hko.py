"""Live end-to-end verification of the HKO weather fetcher.

Fetches REAL data from the Hong Kong Observatory OpenData API, runs it through
the HKOClient transform, and asserts the standardized internal Weather structure
comes back populated. This is the actual deliverable check for the backend
fetcher task (not a mocked test).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.clients.hko import HKOClient


def main() -> int:
    for lang in ("en", "tc", "sc"):
        print(f"\n=== lang={lang} ===")
        c = HKOClient(lang=lang)
        w = c.get_current_weather()
        assert w is not None, f"current weather was None for lang={lang}"
        assert w.temperature and w.temperature.get("value") is not None, "no temperature"
        assert w.humidity and w.humidity.get("value") is not None, "no humidity"
        assert isinstance(w.icon, list) and w.icon, "no icon codes"
        print("temperature:", w.temperature)
        print("humidity:", w.humidity)
        print("icon:", w.icon, "description:", w.description)
        print("update_time:", w.update_time)
        print("warnings:", [(x.code, x.severity) for x in w.warnings])

        ws = c.get_weather_warnings()
        assert isinstance(ws, list)
        for x in ws[:3]:
            t = x.title.en if (x.title and x.title.en) else None
            print("  warn:", x.code, "|", x.severity, "|", t)

    print("\n=== 9-day forecast (en) ===")
    c = HKOClient(lang="en")
    f = c.get_9day_forecast()
    assert f is not None, "9-day forecast returned None"
    print("forecast days:", len(f))
    print("first:", f[0])

    print("\nALL LIVE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
