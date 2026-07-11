"""Dedicated Hong Kong weather endpoint (HKO integration).

Implements:
  * ``GET /api/v1/weather/hk``      -> current weather + active warnings (+ optional
    9-day forecast) for Hong Kong, served through a cross-request TTL cache.
  * ``GET /api/v1/weather/hk/warnings`` -> the active warnings only (also cached).

Both accept the shared ``lang`` query parameter (``en`` / ``tc`` / ``sc``) and
follow the existing fail-soft contract: a missing current-weather feed surfaces
as a 500 ``UPSTREAM_ERROR`` envelope (clear error, not a silent empty payload),
while the warnings endpoint degrades to an empty list.
"""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from config import settings
from models import Weather, WeatherWarning, Error
from src.services import WeatherApiService
from src.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/weather/hk", tags=["Weather (HK)"])

# One service instance per process: it owns the endpoint-level TTL cache, so it
# must live across requests to actually shield HKO from rate-limiting.
_service = WeatherApiService(cache_ttl=settings.cache_ttl_weather_api)


def _error_response(status_code: int, code: str, message: str, detail: str | None = None):
    return JSONResponse(
        status_code=status_code,
        content=Error(code=code, message=message, detail=detail).model_dump(mode="json"),
    )


@router.get(
    "",
    response_model=Weather,
    operation_id="getWeatherHk",
    summary="Get current Hong Kong weather, warnings, and optional forecast",
    responses={
        500: {"model": Error, "description": "Internal/upstream error (HKO feed unreachable)."},
    },
)
def get_weather_hk(
    lang: str = Query("en", description="Language for text fields. One of en / tc / sc."),
    include_forecast: bool = Query(False, description="Attach the 9-day forecast to the response."),
):
    """Return current HK weather + active warnings (+ optional forecast) from HKO.

    Results are served from a process-wide TTL cache (see
    ``settings.cache_ttl_weather_api``, default 10 min) to avoid rate-limiting.
    Fail-soft: if the core current-weather feed is down the endpoint returns a
    500 ``UPSTREAM_ERROR`` so consumers get a clear signal rather than a
    silently empty payload.
    """
    try:
        weather = _service.get_weather(lang=lang, include_forecast=include_forecast)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected error assembling HK weather payload: %s", exc)
        return _error_response(
            status_code=500,
            code="SERVER_ERROR",
            message="Failed to assemble HK weather payload.",
            detail=str(exc),
        )
    if weather is None:
        return _error_response(
            status_code=500,
            code="UPSTREAM_ERROR",
            message="HKO current weather feed unavailable.",
        )
    return weather


@router.get(
    "/warnings",
    response_model=list[WeatherWarning],
    operation_id="getWeatherHkWarnings",
    summary="Get active Hong Kong weather warnings only",
)
def get_weather_hk_warnings(
    lang: str = Query("en", description="Language for text fields. One of en / tc / sc."),
):
    """Return only the currently active HKO weather warnings (cached).

    Degrades to an empty list if the warnings feed is unreachable.
    """
    try:
        warnings = _service.get_warnings(lang=lang)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected error assembling HK weather warnings: %s", exc)
        return _error_response(
            status_code=500,
            code="SERVER_ERROR",
            message="Failed to assemble HK weather warnings.",
            detail=str(exc),
        )
    return warnings
