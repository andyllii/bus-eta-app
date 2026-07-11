"""API route package.

Exposes the canonical routers (matching bus-eta-openapi.yaml) plus legacy
``/v1/...`` aliases for endpoints that were originally mounted without the
``/api`` prefix. The alias routers reuse the same handler functions so their
behaviour is identical to the canonical routes.
"""
from fastapi import APIRouter

from .eta import router as eta_router
from .eta_aggregate import router as eta_aggregate_router
from .health import router as health_router
from .bus_stops import router as bus_stops_router
from .weather import router as weather_router
from .weather_hk import router as weather_hk_router
from .data import router as incidents_router
from .search import router as search_router

# --- Legacy /v1/... aliases (same handlers, deprecated prefix) --------------
from .weather import get_weather, get_weather_warnings
from .data import get_incidents
from .bus_stops import get_bus_stop_combined

# /v1/weather  (+ /v1/weather/warnings) — legacy alias of /api/v1/weather
weather_alias_router = APIRouter(prefix="/v1/weather", tags=["Weather (legacy)"])
weather_alias_router.get(
    "", response_model=weather_router.routes[0].response_model, operation_id="getWeatherLegacy"
)(get_weather)
weather_alias_router.get(
    "/warnings", response_model=dict, operation_id="getWeatherWarningsLegacy"
)(get_weather_warnings)

# /v1/incidents — legacy alias of /api/v1/incidents
incidents_alias_router = APIRouter(prefix="/v1", tags=["Incidents (legacy)"])
incidents_alias_router.get(
    "/incidents", response_model=list, operation_id="getIncidentsLegacy"
)(get_incidents)

# /v1/bus-stops/{stopId} — legacy alias of /api/v1/bus-stops/{stopId}
bus_stops_alias_router = APIRouter(prefix="/v1/bus-stops", tags=["BusStops (legacy)"])
bus_stops_alias_router.get(
    "/{stopId}",
    response_model=bus_stops_router.routes[0].response_model,
    operation_id="getBusStopCombinedLegacy",
)(get_bus_stop_combined)

__all__ = [
    "eta_router",
    "eta_aggregate_router",
    "health_router",
    "bus_stops_router",
    "weather_router",
    "weather_hk_router",
    "incidents_router",
    "search_router",
    "weather_alias_router",
    "incidents_alias_router",
    "bus_stops_alias_router",
]
