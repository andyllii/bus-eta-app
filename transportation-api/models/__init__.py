"""Pydantic response models for API routes.

Two layers live here:

* The *canonical* resource schemas (BusStop, Route, ETA, Weather, Incident, …)
  defined in ``schemas.py`` — these are the typed contract from the OpenAPI
  spec / DESIGN.md and are what the ``/v1`` routes serialize.
* The legacy response models (HealthStatus, EtaItem, EtaResponse) kept for the
  existing ``/health`` and legacy ``/eta`` endpoints.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Any
from datetime import datetime

# --- Canonical resource schemas (OpenAPI / DESIGN.md) ---
from .schemas import (
    Lang,
    MultilingualText,
    GeoPoint,
    BusStop,
    Route,
    ETA,
    WeatherWarning,
    Weather,
    ForecastDay,
    Incident,
    BusStopCombined,
    EtaQuery,
    EtaAggregate,
    SearchStop,
    SearchRoute,
    SearchResponse,
    Error,
)

# --- Legacy / meta models ---
class HealthStatus(BaseModel):
    status: str = "ok"
    app_name: str
    app_version: str
    timestamp: datetime


class EtaItem(BaseModel):
    route: str
    dest: str
    minutes_remaining: Optional[int]
    eta_time: Optional[str]
    remark: str


class EtaResponse(BaseModel):
    query_time: datetime
    bus_eta: List[EtaItem] = Field(default_factory=list)
    weather_warnings: List[str] = Field(default_factory=list)
    traffic_incidents: List[Any] = Field(default_factory=list)


__all__ = [
    # canonical schemas
    "Lang",
    "MultilingualText",
    "GeoPoint",
    "BusStop",
    "Route",
    "ETA",
    "WeatherWarning",
    "Weather",
    "Incident",
    "BusStopCombined",
    "EtaAggregate",
    "EtaQuery",
    "Error",
    # legacy / meta
    "HealthStatus",
    "EtaItem",
    "EtaResponse",
]
