"""
Canonical API data models for the Bus ETA service.

These are the *resource* schemas described in bus-eta-openapi.yaml / DESIGN.md.
They are intentionally decoupled from the wire/transport layer (the client
modules under src/clients define their own raw pydantic models keyed by the
providers' field names). The models here are the stable, typed contract the
HTTP routes serialize.

They do not require a live database: they are plain pydantic models that can be
constructed from raw client data, served as JSON, and validated. A future
persistence layer can subclass or wrap these.

Source of truth:
  - bus-eta-openapi.yaml (OpenAPI 3.0.3)
  - DESIGN.md  §2 Core Data Models
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared building blocks
# ---------------------------------------------------------------------------
class Lang(str, Enum):
    """Supported response languages (HKO / TD / KMB all serve these)."""

    EN = "en"
    TC = "tc"
    SC = "sc"


class MultilingualText(BaseModel):
    """Human-readable text in three languages.

    Mirrors the {en, tc, sc} object used throughout the OpenAPI spec.
    All three are optional at the model level so a provider that only
    returns Chinese can still populate a valid object; endpoints that
    require a value (e.g. BusStop.name) should enforce it through the
    owning model's `required` list.
    """

    en: Optional[str] = None
    tc: Optional[str] = None
    sc: Optional[str] = None

    @classmethod
    def from_tc(cls, tc: str) -> "MultilingualText":
        """Convenience factory when only Traditional Chinese is known."""
        return cls(tc=tc)

    def is_empty(self) -> bool:
        """True when none of the three languages carry any text."""
        return not (self.en or self.tc or self.sc)


class GeoPoint(BaseModel):
    """WGS84 geographic coordinate."""

    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


# ---------------------------------------------------------------------------
# Core resource models
# ---------------------------------------------------------------------------
class BusStop(BaseModel):
    """A physical bus stop (core static resource)."""

    id: str = Field(
        ...,
        description="Unique KMB stop ID (16-char hex), e.g. 946C74E30100FE80.",
        examples=["946C74E30100FE80"],
    )
    name: MultilingualText
    location: GeoPoint
    address: Optional[MultilingualText] = None
    routes: List[str] = Field(
        default_factory=list,
        description="Route numbers serving this stop.",
        examples=[["1", "2", "6"]],
    )
    data_timestamp: Optional[datetime] = Field(
        None, description="When the stop metadata was last refreshed."
    )


class Route(BaseModel):
    """A bus route definition."""

    id: str = Field(
        ..., description="Route number (uppercase).", examples=["1"]
    )
    name: Optional[MultilingualText] = None
    operator: str = Field(..., description="Operating company code, e.g. KMB.", examples=["KMB"])
    service_type: int = Field(1, description="KMB service type (1=normal, 2=express, ...).")
    directions: List[str] = Field(
        default_factory=list, description="Direction codes, e.g. ['O','I'].", examples=[["O", "I"]]
    )
    destinations: dict = Field(
        ...,
        description="Terminal names per direction, e.g. {'O': ..., 'I': ...}.",
    )
    stops: Optional[List[str]] = Field(
        None, description="Ordered stop IDs for the route (optional expansion)."
    )


class ETA(BaseModel):
    """Estimated time of arrival for a route at a stop (derived from KMB feed)."""

    co: str = Field(..., description="Company code, e.g. KMB.", examples=["KMB"])
    route: str = Field(..., examples=["1"])
    direction: str = Field(..., description="O = outbound, I = inbound.", examples=["O"])
    service_type: int = Field(1)
    seq: int = Field(..., description="Stop sequence number on the route.")
    dest: MultilingualText
    eta_seq: int = Field(..., description="Ordering index among upcoming arrivals.")
    eta: Optional[datetime] = Field(None, description="Predicted arrival timestamp (UTC).")
    minutes_remaining: Optional[int] = Field(
        None,
        ge=0,
        description="Minutes until arrival, computed server-side (>=0). Null when eta is null.",
    )
    remark: Optional[MultilingualText] = Field(
        None, description="Human remark, e.g. 'Scheduled', 'KMB staff on board'."
    )
    data_timestamp: Optional[datetime] = Field(
        None, description="When KMB last published this prediction."
    )


class WeatherWarning(BaseModel):
    """A single active HKO weather warning."""

    code: str = Field(..., description="HKO warning code, e.g. WRAINA.", examples=["WRAINA"])
    title: MultilingualText
    severity: str = Field(
        ...,
        description="none / amber / red / black / warning",
        examples=["amber"],
    )
    contents: Optional[str] = Field(None, description="Full warning text issued by HKO.")
    issue_time: Optional[datetime] = Field(None)


class ForecastDay(BaseModel):
    """A single day from the HKO 9-day forecast (optional enrichment)."""

    date: Optional[str] = Field(None, description="Forecast date (YYYYMMDD).")
    week: Optional[str] = Field(None, description="Day of week, localised.")
    weather: Optional[str] = Field(None, description="Forecast weather text.")
    max_temp: Optional[float] = Field(None, description="Forecast maximum temperature.")
    min_temp: Optional[float] = Field(None, description="Forecast minimum temperature.")


class Weather(BaseModel):
    """Current weather, warnings, and forecast (HKO)."""

    temperature: Optional[dict] = Field(
        None, description="{'place': ..., 'value': ..., 'unit': ...}."
    )
    description: Optional[str] = Field(
        None,
        description=(
            "Human-readable description of the current conditions, e.g. "
            "'Showers' / '多雲' / '多云'. Resolved to the requested language and "
            "derived from the HKO weather-icon codes (see "
            "src.clients.hko._WEATHER_ICON_DESC)."
        ),
    )
    humidity: Optional[dict] = Field(None, description="{'value': ..., 'unit': ...}.")
    icon: List[int] = Field(default_factory=list, description="HKO weather icon codes.")
    update_time: Optional[datetime] = Field(None, description="Feed update time.")
    warnings: List[WeatherWarning] = Field(
        default_factory=list,
        description=(
            "Active warnings. Each carries a warning `code` (its type, e.g. "
            "WRAINA) and a `severity` (its level: none/amber/red/black/warning)."
        ),
    )
    forecast: Optional[List[ForecastDay]] = Field(None, description="Short forecast (optional).")


class Incident(BaseModel):
    """A traffic incident from the HK Transport Department."""

    id: str = Field(..., description="TD incident number.", examples=["TD20260710-00123"])
    heading: MultilingualText
    detail: Optional[MultilingualText] = None
    location: MultilingualText
    district: Optional[MultilingualText] = None
    direction: Optional[MultilingualText] = None
    road_type: Optional[MultilingualText] = None
    near_landmark: Optional[MultilingualText] = None
    status: MultilingualText = Field(
        ..., description="INCIDENT_STATUS_* textual value, e.g. ACTIVE / 生效中."
    )
    announcement_date: Optional[str] = Field(
        None, description="e.g. '2026-07-10 08:30'.", examples=["2026-07-10 08:30"]
    )
    relevance: Optional[str] = Field(
        None,
        description="high / medium / low / none — server-computed on combined endpoints.",
    )
    content: Optional[MultilingualText] = Field(
        None,
        description="Full incident narrative / impact text (TD CONTENT_* field).",
    )
    source_id: Optional[str] = Field(
        None, description="Numeric message id assigned by the TD feed (element <ID>)."
    )
    geo: Optional[GeoPoint] = Field(
        None, description="WGS84 coordinate when the feed provides LATITUDE/LONGITUDE."
    )


# ---------------------------------------------------------------------------
# Aggregation / error models
# ---------------------------------------------------------------------------
class BusStopCombined(BaseModel):
    """PRIMARY combined response for a bus stop.

    Aggregates stop details, ETAs, weather, and incidents relevant to that
    stop. This is the payload the mobile stop screen consumes.
    """

    stop: BusStop
    etas: List[ETA] = Field(default_factory=list)
    weather: Optional[Weather] = None
    incidents: List[Incident] = Field(default_factory=list)
    query_time: datetime = Field(..., description="Server time the response was assembled (UTC).")


class EtaQuery(BaseModel):
    """Echo of the resolved query parameters for ``GET /api/v1/eta``."""

    route: str = Field(..., description="Route number that was requested.")
    stop_id: str = Field(..., description="Stop id that was requested.")
    operator: Optional[str] = Field(
        None,
        description="Resolved operator (KMB / CTB / NWFB), or None if the stop is unknown.",
    )
    lang: str = Field("tc", description="Language used for the response text.")


class EtaAggregate(BaseModel):
    """Combined response for ``GET /api/v1/eta`` — the primary aggregation endpoint.

    Accepts a bus ``route`` + ``stop`` and returns a single object containing
    the next few bus arrivals, the current weather, and any traffic incidents
    that might affect the route, so the frontend can render one screen from one
    call. Built by :class:`src.services.eta_aggregate.EtaAggregateService`.
    """

    query: EtaQuery
    etas: List[ETA] = Field(
        default_factory=list, description="Upcoming arrivals for the route at the stop."
    )
    weather: Optional[Weather] = Field(
        None, description="Current HKO weather + active warnings (null if degraded)."
    )
    incidents: List[Incident] = Field(
        default_factory=list,
        description=(
            "Traffic incidents relevant to the route/stop, each tagged with a "
            "server-computed `relevance` (high/medium/low), sorted high-first."
        ),
    )
    query_time: datetime = Field(..., description="Server time the response was assembled (UTC).")
    degraded: bool = Field(
        False,
        description=(
            "True when one or more providers failed and were skipped (partial "
            "data returned). Mirrors the fail-soft aggregation policy."
        ),
    )


class SearchStop(BaseModel):
    """A single stop match from ``GET /api/v1/search``."""
    id: str = Field(
        ...,
        description="Stop id (KMB 16-char hex / Citybus 6-digit numeric).",
        examples=["946C74E30100FE80"],
    )
    name: MultilingualText
    address: Optional[MultilingualText] = None
    location: Optional[GeoPoint] = None
    routes: List[str] = Field(default_factory=list, description="Route numbers serving this stop.")
    kind: str = Field("stop", description="Discriminator used by the UI ('stop').")
    operator: Optional[str] = Field(
        None, description="Resolved operator code (KMB/CTB/NWFB) or None when unknown."
    )


class SearchRoute(BaseModel):
    """A single route match from ``GET /api/v1/search``."""
    id: str = Field(..., description="Route number (uppercase).", examples=["1"])
    operator: str = Field(..., description="Operating company code, e.g. KMB.", examples=["KMB"])
    kind: str = Field("route", description="Discriminator used by the UI ('route').")
    name: Optional[MultilingualText] = None
    destinations: dict = Field(
        default_factory=dict, description="Terminal names per direction, e.g. {'O': ..., 'I': ...}."
    )


class SearchResponse(BaseModel):
    """Unified autocomplete payload for the Search screen.

    One call returns both stop and route matches so the mobile UI can render a
    single mixed results list and route the user into the combined Results view
    with the correct ``route``/``stopId`` parameters on selection.
    """
    query: str = Field(..., description="Echo of the normalised query string.")
    lang: str = Field("tc", description="Language used for the returned text fields.")
    total: int = Field(..., description="Total number of matches (stops + routes).")
    stops: List[SearchStop] = Field(default_factory=list)
    routes: List[SearchRoute] = Field(default_factory=list)


class Error(BaseModel):
    """Standard error envelope returned by all error responses."""
    code: str = Field(..., examples=["RESOURCE_NOT_FOUND"])
    message: str
    detail: Optional[str] = None


__all__ = [
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
    "EtaQuery",
    "EtaAggregate",
    "Error",
]
