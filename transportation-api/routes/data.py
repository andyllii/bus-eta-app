"""Standalone traffic-incident endpoint (Transport Department feed).

Exposes the active road incidents from the Hong Kong Transport Department XML
feed directly (Hong Kong–wide, not tied to a single stop) so clients can render
traffic alerts independently of the combined bus-stop view. Weather is served
by ``routes/weather.py`` (``GET /v1/weather``), so this module owns only the
incidents route.

The endpoint supports optional ``district`` / ``status`` filters (case-
insensitive substring match across the three languages) so the mobile traffic-
alert screen can narrow to a region or to newly-reported incidents. Incident
fetching is served through the :class:`IncidentService`, which in turn uses the
TTL-cached :class:`TDClient`.
"""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from config import settings
from models import Error, Incident
from src.clients import TDClient
from src.logging_config import get_logger
from src.services import IncidentService

logger = get_logger(__name__)

# Canonical prefix from bus-eta-openapi.yaml. A "/v1" alias is registered in
# app.py so the previously-documented "/v1/incidents" path keeps working.
router = APIRouter(prefix="/api/v1", tags=["Incidents"])

# One service per process: it owns the cached TD client so upstream load stays
# low across requests.
_service = IncidentService(lang=settings.default_lang)


def _error_response(status_code: int, code: str, message: str, detail: str | None = None):
    return JSONResponse(
        status_code=status_code,
        content=Error(code=code, message=message, detail=detail).model_dump(mode="json"),
    )


@router.get(
    "/incidents",
    response_model=list[Incident],
    operation_id="getIncidents",
    summary="Active traffic incidents from the Transport Department (Hong Kong-wide)",
    responses={500: {"model": Error, "description": "TD feed unavailable."}},
)
def get_incidents(
    lang: str = Query("tc", description="One of en / tc / sc."),
    district: str | None = Query(None, description="Case-insensitive district substring filter (en/tc/sc)."),
    status: str | None = Query(None, description="Case-insensitive status substring filter (e.g. 'new')."),
):
    """Return active road incidents from the Transport Department XML feed.

    Results are cached (``settings.cache_ttl_incidents``, default 120s) to keep
    upstream load low. Fail-soft: if the TD feed is unreachable the endpoint
    returns a 500 ``UPSTREAM_ERROR`` envelope so consumers get a clear signal
    rather than a silently empty payload.
    """
    # Honour a per-request language without rebuilding the whole service.
    client = TDClient(lang=lang)
    service = IncidentService(lang=lang, td=client)
    try:
        incidents = service.get_incidents(district=district, status=status)
    except Exception as exc:  # noqa: BLE001
        logger.exception("TD incidents fetch failed")
        return _error_response(500, "UPSTREAM_ERROR", "TD traffic feed unavailable.", detail=str(exc))
    return incidents
