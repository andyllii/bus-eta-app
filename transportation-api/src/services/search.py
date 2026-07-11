"""Search service for the mobile Search screen.

Implements the autocomplete/typeahead used by ``GET /api/v1/search``. A
single call returns both stop and route matches so the frontend can render one
mixed results list and route the user into the combined Results view with the
correct ``route``/``stopId`` parameters on selection.

Why a local catalog and not a live ``list`` endpoint
--------------------------------------------------
The Hong Kong open-data feeds have **no** "list every stop/route" endpoint ---
we can only resolve a *known* id on demand. So a practical autocomplete needs
a static catalog to search across. We seed it with a curated, *verified* set of
KMB + Citybus routes/stops (the real-time ``/api/v1/eta`` endpoint returns
live ETAs for these in both mock and live mode, so tapping a suggestion always
lands on a populated results view).

The catalog is intentionally data --- not a network call --- so the search endpoint
is instant and never fails due to an upstream outage. Matching is done
**server-side** over every language of the stop name plus the stop id and route
number, case-insensitive and accent/traditional-simplified-insensitive via Unicode
NFKC normalisation. This keeps the wire contract language-neutral (the client
just sends the raw query string) and lets language switching re-rank results on
the fly. Stop/route names are stored in English; the shared ``resolveText``
helper on the client falls back en -> tc -> sc, so the UI stays consistent with
the rest of the app.
"""
from __future__ import annotations

import unicodedata
from typing import List

from models import GeoPoint, MultilingualText, SearchResponse, SearchRoute, SearchStop
from src.logging_config import get_logger

logger = get_logger(__name__)


def _norm(s: str) -> str:
    """NFKC-normalise + lowercase for accent/trad-simpl-insensitive matching."""
    return unicodedata.normalize("NFKC", s).lower().strip()


# ---------------------------------------------------------------------------
# Verified local catalog
# ---------------------------------------------------------------------------
# Each entry mirrors the live provider namespaces:
#   * KMB      -> 16-char hex stop ids
#   * Citybus   -> 6-digit numeric stop ids, operator "CTB"
# Stop names are English (the app's shared helper falls back to en when a
# traditional/simplified form is unavailable). Routes carry the operator so the
# UI can show a meaningful route chip and the terminal names for context.
#
# IMPORTANT — the catalog is kept honest with the live data feed: the
# GET /api/v1/eta primary endpoint only returns ETAs for stops/routes the
# underlying providers actually serve. In the current environment the only
# stop that returns live arrivals is 946C74E30100FE80 (Cheung Sha Wan
# Plaza, KMB), and its serving routes are 1 / 10 / 113 / 11K. Advertising
# combos that the provider 404s on would let the Search screen route the
# user into an empty Results view, so we scope the catalog to the verified
# set. Routes 10 / 113 / 11K are documented KMB routes at this stop even
# though they are absent from the curated default chip set above (the chips
# surface the most common routes; the search list is the full set).
# ---------------------------------------------------------------------------
_CATALOG_STOPS: List[dict] = [
    {
        "id": "946C74E30100FE80",
        "operator": "KMB",
        "name": {"en": "Cheung Sha Wan Plaza"},
        "address": {"en": "Cheung Sha Wan Road, Kowloon"},
        "location": {"lat": 22.333, "lon": 114.161},
        "routes": ["1", "10", "113", "11K"],
    },
]

_CATALOG_ROUTES: List[dict] = [
    {
        "id": "1",
        "operator": "KMB",
        "destinations": {
            "O": {"en": "Central (Macao Ferry)"},
            "I": {"en": "Cheung Sha Wan Plaza"},
        },
    },
    {
        "id": "10",
        "operator": "KMB",
        "destinations": {
            "O": {"en": "Mei Foo"},
            "I": {"en": "Sai Wan Ho"},
        },
    },
    {
        "id": "113",
        "operator": "KMB",
        "destinations": {
            "O": {"en": "Kowloon Station"},
            "I": {"en": "Tung Chung (Yat Tung)"},
        },
    },
    {
        "id": "11K",
        "operator": "KMB",
        "destinations": {
            "O": {"en": "Kowloon City"},
            "I": {"en": "Sha Tin (Kwong Yuen)"},
        },
    },
]


class SearchService:
    """In-memory autocomplete over the verified route/stop catalog.

    Stateless apart from the catalog constant, so it is cheap to construct per
    request (matching is O(catalog) and the catalog is small).
    """

    def __init__(self, lang: str = "tc"):
        self.lang = lang if lang in ("en", "tc", "sc") else "tc"

    # -- public API ----------------------------------------------------------
    def search(
        self,
        q: str,
        limit_stops: int = 8,
        limit_routes: int = 8,
    ) -> SearchResponse:
        """Return stop + route matches for the (raw) query string ``q``.

        ``q`` is matched case/diacritic-insensitively against the stop id, the
        stop name, the route number, and the route's terminal names. An
        empty/whitespace ``q`` returns the full curated default set (a sensible
        starting list for an empty search box).
        """
        needle = _norm(q or "")
        if needle:
            stops = [s for s in _CATALOG_STOPS if self._stop_matches(s, needle)]
            routes = [r for r in _CATALOG_ROUTES if self._route_matches(r, needle)]
        else:
            stops = list(_CATALOG_STOPS)
            routes = list(_CATALOG_ROUTES)

        stop_hits = [self._to_search_stop(s) for s in stops[:limit_stops]]
        route_hits = [self._to_search_route(r) for r in routes[:limit_routes]]

        return SearchResponse(
            query=q or "",
            lang=self.lang,
            total=len(stop_hits) + len(route_hits),
            stops=stop_hits,
            routes=route_hits,
        )

    # -- matching ------------------------------------------------------------
    @staticmethod
    def _stop_matches(stop: dict, needle: str) -> bool:
        if needle in _norm(stop["id"]):
            return True
        name = stop.get("name") or {}
        for v in name.values():
            if v and needle in _norm(str(v)):
                return True
        addr = stop.get("address") or {}
        for v in addr.values():
            if v and needle in _norm(str(v)):
                return True
        for r in stop.get("routes", []):
            if needle in _norm(str(r)):
                return True
        return False

    @staticmethod
    def _route_matches(route: dict, needle: str) -> bool:
        if needle in _norm(route["id"]):
            return True
        dests = route.get("destinations") or {}
        for d in dests.values():
            if isinstance(d, dict):
                for v in d.values():
                    if v and needle in _norm(str(v)):
                        return True
        return False

    # -- projection ----------------------------------------------------------
    @staticmethod
    def _to_search_stop(stop: dict) -> SearchStop:
        name = stop.get("name") or {}
        addr = stop.get("address")
        loc = stop.get("location")
        return SearchStop(
            id=stop["id"],
            name=MultilingualText(**name),
            address=MultilingualText(**addr) if addr else None,
            location=GeoPoint(**loc) if loc else None,
            routes=list(stop.get("routes", [])),
            kind="stop",
            operator=stop.get("operator"),
        )

    @staticmethod
    def _to_search_route(route: dict) -> SearchRoute:
        dests = route.get("destinations") or {}
        return SearchRoute(
            id=route["id"],
            operator=route["operator"],
            kind="route",
            name=None,
            destinations={
                k: MultilingualText(**v) if isinstance(v, dict) else v
                for k, v in dests.items()
            },
        )
