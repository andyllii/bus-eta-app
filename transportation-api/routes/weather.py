"""Weather routes (HKO integration).

Implements (canonical, from bus-eta-openapi.yaml):
  * ``GET /api/v1/weather``         -> current weather, active warnings, and an
    optional 9-day forecast (spec operationId ``getWeather``).
  * ``GET /api/v1/weather/warnings`` -> the active warnings only
    (spec operationId ``getWeatherWarnings``).

A legacy ``/v1/weather`` (+ ``/v1/weather/warnings``) alias is also mounted in
app.py using the same handlers, so clients that predate the canonical prefix
keep working.

Both accept the shared ``lang`` query parameter and are **fail-soft**: if the
HKO feed is unreachable the endpoints still respond 200 with whatever could be
recovered (``weather=None`` / empty ``warnings``), matching the DESIGN.md
aggregation principle. A hard failure (e.g. misconfigured base URL) surfaces as
a 500 ``SERVER_ERROR`` envelope.
"""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from config import settings
from models import Weather, WeatherWarning, Error
from src.clients import HKOClient
from src.logging_config import get_logger

logger = get_logger(__name__)

# Canonical prefix from bus-eta-openapi.yaml. A "/v1/weather" alias is
# registered in app.py so the previously-documented path keeps working.
router = APIRouter(prefix="/api/v1/weather", tags=["Weather"])

# One client per request is cheap; built with the request language so the
# HKO feed and the returned titles respect `lang`.
def _client(lang: str) -> HKOClient:
    return HKOClient(lang=lang)


def _error_response(status_code: int, code: str, message: str, detail: str | None = None):
    return JSONResponse(
        status_code=status_code,
        content=Error(code=code, message=message, detail=detail).model_dump(mode="json"),
    )


@router.get(
    "",
    response_model=Weather,
    operation_id="getWeather",
    summary="Get current weather, warnings, and forecast",
    responses={
        500: {"model": Error, "description": "Internal server error (HKO feed unreachable)."},
    },
)
def get_weather(
    lang: str = Query("tc", description="Language for text fields. One of en / tc / sc."),
    include_forecast: bool = Query(False, description="Attach the 9-day forecast to the response."),
):
    """Return current weather + active warnings (+ optional forecast) from HKO.

    Fail-soft: if the core current-weather feed is down, the payload is still
    returned with a best-effort (possibly empty) warnings list so the mobile
    client can render partial data.
    """
    try:
        client = _client(lang)
        weather = client.get_current_weather()
        if weather is None:
            # Core current-weather feed (rhrread) is down. Fail loud so a
            # consumer of this standalone endpoint gets a clear error rather
            # than a silently empty payload. The combined bus-stop endpoint
            # still degrades gracefully because it calls the client directly
            # under its own try/except (settings.degrade_on_upstream_error).
            logger.error("HKO current weather feed unavailable (lang=%s)", lang)
            return _error_response(
                status_code=500,
                code="UPSTREAM_ERROR",
                message="HKO current weather feed unavailable.",
            )
        if include_forecast:
            fcast = client.get_9day_forecast()
            if fcast is not None:
                weather.forecast = fcast
        return weather
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected error assembling weather payload: %s", exc)
        return _error_response(
            status_code=500,
            code="SERVER_ERROR",
            message="Failed to assemble weather payload.",
            detail=str(exc),
        )


@router.get(
    "/warnings",
    response_model=dict,
    operation_id="getWeatherWarnings",
    summary="Get active weather warnings only",
)
def get_weather_warnings(
    lang: str = Query("tc", description="Language for text fields. One of en / tc / sc."),
):
    """Return only the currently active HKO weather warnings.

    Response shape: ``{"warnings": WeatherWarning[]}`` (matches the OpenAPI
    ``/api/v1/weather/warnings`` schema).
    """
    try:
        client = _client(lang)
        warnings = client.get_weather_warnings()
        return {"warnings": [w.model_dump(mode="json") for w in warnings]}
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected error assembling weather warnings: %s", exc)
        return _error_response(
            status_code=500,
            code="SERVER_ERROR",
            message="Failed to assemble weather warnings.",
            detail=str(exc),
        )
