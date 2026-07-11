"""Live smoke test for the TD incidents fetcher (direct client + service)."""
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.clients import TDClient
from src.services import IncidentService

c = TDClient(lang="tc")
incs = c.get_incidents()
print(f"Fetched {len(incs)} incidents from live TD feed")
for inc in incs[:3]:
    d = inc.model_dump(mode="json")
    print(json.dumps({k: d[k] for k in ("id", "heading", "location", "district", "status", "announcement_date", "source_id", "geo", "content") if d.get(k) is not None}, ensure_ascii=False, indent=2))

svc = IncidentService(td=c)
try:
    filt = svc.get_incidents(status="new")
    print(f"\nStatus='new' filter -> {len(filt)} incidents")
except Exception as e:
    print("filter err", e)
