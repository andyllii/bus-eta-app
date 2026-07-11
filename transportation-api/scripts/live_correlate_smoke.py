"""Live smoke: correlation in the combined bus-stop endpoint."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)
# 946C74E30100FE80 = Cheung Sha Wan Plaza (KMB). Geo ~22.333,114.161.
r = client.get("/v1/bus-stops/946C74E30100FE80?include_weather=false")
print("status:", r.status_code)
data = r.json()
print("stop:", data["stop"]["name"])
for inc in data.get("incidents", []):
    print("  incident", inc["id"], "relevance=", inc.get("relevance"))
