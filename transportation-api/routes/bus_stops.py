"""Combined bus-stop endpoint (PRIMARY endpoint of the API).

Implements ``GET /api/v1/bus-stops/{stopId}`` from bus-eta-openapi.yaml — the
primary endpoint the mobile client calls when a user selects a stop. It
returns a :class:`BusStopCombined` payload (stop details + ETAs + weather +
incidents).

The payload is assembled by :class:`BusStopService` from the live Hong Kong
open-data providers (KMB, Citybus/NWFB, HKO, Transport Department). Stop-id
format decides which bus company is queried:
  * 16-char hex  -> KMB
  * 6-digit numeric -> Citybus / NWFB

If the stop cannot be resolved (unknown id for every operator) the endpoint
returns ``404`` with the standard ``Error`` envelope. Per-route filtering and
the ``include_weather`` / ``include_incidents`` toggles are honoured.

When ``settings.use_mock_data`` is on (``USE_MOCK_DATA=1``) the endpoint
serves the built-in mock payload for any id, so the API works fully offline.

The canonical path is ``/api/v1/bus-stops``; a ``/v1/bus-stops`` alias is
registered in app.py for backward compatibility.
"""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from config import settings
from models import BusStopCombined, Error
from src.logging_config import get_logger
from src.services import BusStopService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/bus-stops", tags=["BusStops", "Aggregation"])


def _error_response(status_code: int, code: str, message: str, detail: str | None = None):
    return JSONResponse(
        status_code=status_code,
        content=Error(code=code, message=message, detail=detail).model_dump(mode="json"),
    )


@router.get(
    "/{stopId}",
    response_model=BusStopCombined,
    operation_id="getBusStopCombined",
    summary="Get combined data for a bus stop (PRIMARY endpoint)",
    responses={
        404: {"model": Error, "description": "The requested bus stop was not found."},
        500: {"model": Error, "description": "Internal server error (e.g. an upstream provider failed)."},
    },
)
def get_bus_stop_combined(
    stopId: str,
    lang: str = Query("tc", description="Language for text fields. One of en / tc / sc."),
    route: str | None = Query(None, description="Optional filter to return only ETAs for a single route."),
    include_weather: bool = Query(True, description="Include the Weather block."),
    include_incidents: bool = Query(True, description="Include the Incidents block."),
):
    """Return combined ETA + weather + incident data for a bus stop."""
    service = BusStopService(lang=lang)
    try:
        combined = service.get_combined(stopId, route=route)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to assemble combined data for %s", stopId)
        return _error_response(
            status_code=500,
            code="UPSTREAM_ERROR",
            message="Failed to assemble bus stop data.",
            detail=str(exc),
        )

    if combined is None:
        logger.warning("Unknown stopId requested: %s", stopId)
        return _error_response(
            status_code=404,
            code="RESOURCE_NOT_FOUND",
            message=f"Bus stop {stopId} not found.",
            detail="No operator (KMB / Citybus / NWFB) returned a stop with this id.",
        )

    # Optional block toggles (applied after aggregation).
    if not include_weather:
        combined.weather = None
    if not include_incidents:
        combined.incidents = []

    logger.info("Served combined data for stop %s (lang=%s, etas=%d)", stopId, lang, len(combined.etas))
    return combined
