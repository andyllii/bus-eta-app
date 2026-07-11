"""Verify the app and all clients import cleanly."""
import app

print("app imported OK;", len(app.app.routes), "routes")
# Touch the clients to ensure they import
from src.clients import KMBClient, CitybusClient, HKOClient, TDClient
from src.services import BusStopService

print("clients + service import OK")
print("route paths:", sorted({getattr(r, 'path', '') for r in app.app.routes if hasattr(r, 'path')}))
