"""Unified search endpoint for the mobile Search screen.

Implements ``GET /api/v1/search?q=&lang=`` from bus-eta-openapi.yaml
(operation ``search``). A single call returns both matching bus **stops** and
**routes** so the mobile UI can render one autocomplete list and route the user
into the combined Results view with the correct ``route``/``stopId`` on selection.

The catalog behind the search is a curated, *verified* set of KMB + Citybus
routes/stops (the live ``/api/v1/eta`` endpoint returns ETAs for these in
both mock and live mode). Matching is done server-side across every language of
the stop name, the stop id, the route number and the route's terminals — so the
client simply forwards the raw query string and the wire contract stays
language-neutral. See :class:`src.services.search.SearchService` for the
catalog and matching details.

The endpoint is data-backed (no upstream calls), so it is instant and never
fails due to an upstream outage.
"""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from config import settings
from models import Error, SearchResponse
from src.logging_config import get_logger
from src.services import SearchService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Search"])


def _error_response(status_code: int, code: str, message: str, detail: str | None = None):
    return JSONResponse(
        status_code=status_code,
        content=Error(code=code, message=message, detail=detail).model_dump(mode="json"),
    )


@router.get(
    "/search",
    response_model=SearchResponse,
    operation_id="search",
    summary="Search bus routes and stops (autocomplete for the Search screen)",
    responses={
        500: {"model": Error, "description": "Internal server error."},
    },
)
def search(
    q: str = Query("", description="Free-text query: stop name, stop id, or route number."),
    lang: str = Query("tc", description="Language for text fields. One of en / tc / sc."),
    limit_stops: int = Query(8, ge=0, le=50, description="Max stop matches to return."),
    limit_routes: int = Query(8, ge=0, le=50, description="Max route matches to return."),
):
    """Return stop + route autocomplete matches for ``q``.

    An empty ``q`` returns the full curated default set (common stops + routes),
    which the Search screen uses to seed an empty search box.
    """
    try:
        service = SearchService(lang=lang)
        result = service.search(q, limit_stops=limit_stops, limit_routes=limit_routes)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Search failed for q=%r lang=%s", q, lang)
        return _error_response(
            status_code=500,
            code="INTERNAL_ERROR",
            message="Search failed.",
            detail=str(exc),
        )
    logger.info("Search q=%r lang=%s -> %d matches", q, lang, result.total)
    return result
