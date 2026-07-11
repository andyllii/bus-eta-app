"""Smoke-test the legacy /eta route (uses deprecated attribute names)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings

settings.use_mock_data = False

from fastapi.testclient import TestClient

from app import app

c = TestClient(app)
r = c.get("/eta?route=1&stop_id=946C74E30100FE80")
print("status", r.status_code)
print(r.text[:800])
