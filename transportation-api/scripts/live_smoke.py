"""Live smoke test: hit the real TD feed through the full stack.

Run:  .venv/bin/python scripts/live_smoke.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

print("=== GET /v1/incidents (live TD feed) ===")
r = client.get("/v1/incidents")
print("status:", r.status_code)
data = r.json()
print("count:", len(data))
if data:
    inc = data[0]
    print("first id:", inc["id"])
    print("heading:", inc["heading"])
    print("location:", inc["location"])
    print("status:", inc["status"], "relevance:", inc["relevance"])
    print("content present:", inc.get("content") is not None)
    print("source_id:", inc.get("source_id"))

print("\n=== GET /v1/incidents?lang=en&status=new ===")
r2 = client.get("/v1/incidents?lang=en&status=new")
print("status:", r2.status_code, "count:", len(r2.json()))
