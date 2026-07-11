"""Primary aggregation endpoint ``GET /api/v1/eta``.

This is the endpoint the frontend calls to render a single "next bus" board: it
takes a bus ``route`` and ``stop`` and returns one JSON object containing:

  1. the next few bus arrival times (``etas``),
  2. the current weather (``weather``), and
  3. any traffic incidents that might affect the route (``incidents``), each
     tagged with a server-computed ``relevance`` (high / medium / low), sorted
     high-first.

The payload is assembled by :class:`src.services.eta_aggregate.EtaAggregateService`
which fetches the three providers concurrently and serves the result from a
process-wide TTL cache.

Resolution strategy
-------------------
Hong Kong operators use disjoint stop-ID namespaces:
  * KMB      — 16-char hex ids (e.g. ``946C74E30100FE80``)
  * Citybus  — 6-digit numeric ids (e.g. ``001027``)

The service inspects the id shape to decide which stop clients to query.

Behaviour
---------
* Unknown ``stop`` / ``route`` (no ETA returned by any operator) -> ``404``
  with the standard ``Error`` envelope (``RESOURCE_NOT_FOUND``).
* Missing ``route`` or ``stop`` query param -> ``422`` (FastAPI validation).
* Per-request ``include_weather`` / ``include_incidents`` toggles omit a block.
* Fail-soft: if weather or incidents fails while ETAs are present, the partial
  payload is returned with ``degraded: true`` (HTTP ``200``). Set
  ``degrade=false`` (query) to force a ``500`` instead.

When ``settings.use_mock_data`` is on the endpoint serves the built-in mock for
any id, so the API works fully offline.
"""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from config import settings
from models import EtaAggregate, Error
from src.logging_config import get_logger
from src.services import EtaAggregateService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Aggregation"])

# One service per process: it owns the TTL cache + the cached upstream clients,
# so upstream load stays low across requests.
_service = EtaAggregateService(lang=settings.default_lang)


def _error_response(status_code: int, code: str, message: str, detail: str | None = None):
    return JSONResponse(
        status_code=status_code,
        content=Error(code=code, message=message, detail=detail).model_dump(mode="json"),
    )


@router.get(
    "/eta",
    response_model=EtaAggregate,
    operation_id="getEtaAggregate",
    summary="Combined bus ETA + weather + traffic incidents for a route & stop (PRIMARY aggregation endpoint)",
    responses={
        404: {"model": Error, "description": "The requested route/stop was not found."},
        500: {"model": Error, "description": "Upstream provider failed and degradation is disabled."},
    },
)
def get_eta_aggregate(
    route: str = Query(..., description="Bus route number, e.g. '1'."),
    stop: str = Query(..., description="Bus stop id. KMB = 16-char hex; Citybus/NWFB = 6-digit numeric."),
    lang: str = Query("tc", description="Language for text fields. One of en / tc / sc."),
    include_weather: bool = Query(True, description="Include the Weather block."),
    include_incidents: bool = Query(True, description="Include the Incidents block."),
    degrade: bool = Query(
        True,
        description="Fail-soft: on a partial upstream failure return partial data (degraded=true) instead of 500.",
    ),
):
    """Return combined ETA + weather + incident data for a bus route at a stop.

    The response is a single object with ``etas``, ``weather`` and ``incidents``
    plus an echo of the resolved query (``query``) and a ``degraded`` flag that
    is true when one of the secondary providers (weather/incidents) failed and
    was skipped.
    """
    try:
        aggregate = _service.get_eta_aggregate(
            route=route,
            stop_id=stop,
            lang=lang,
            include_weather=include_weather,
            include_incidents=include_incidents,
            degrade=degrade,
        )
    except Exception as exc:  # noqa: BLE001
        # Distinguish a "stop/route not found" (no ETA) from a real upstream
        # failure so we answer the right status code.
        from src.clients.exceptions import UpstreamError

        if isinstance(exc, UpstreamError) and "No ETA data" in str(exc):
            logger.info("Unknown route/stop requested: route=%s stop=%s", route, stop)
            return _error_response(
                status_code=404,
                code="RESOURCE_NOT_FOUND",
                message=f"No ETA data for route {route} at stop {stop}.",
                detail="No operator (KMB / Citybus / NWFB) returned an ETA for this route+stop.",
            )
        logger.exception("Failed to assemble aggregated ETA data (route=%s, stop=%s)", route, stop)
        return _error_response(
            status_code=500,
            code="UPSTREAM_ERROR",
            message="Failed to assemble aggregated ETA data.",
            detail=str(exc),
        )

    logger.info(
        "Served aggregated ETA (route=%s, stop=%s, lang=%s, etas=%d, degraded=%s)",
        route,
        stop,
        lang,
        len(aggregate.etas),
        aggregate.degraded,
    )
    return aggregate
