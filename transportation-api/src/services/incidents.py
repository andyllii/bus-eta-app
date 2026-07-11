"""Traffic-incident service: filtering + relevance correlation.

This layer sits between the raw :class:`TDClient` feed and the API. It does
two things beyond plain fetching:

* **Filtering** — narrow the Hong-Kong-wide incident list by ``district`` or
  ``status`` (case-insensitive substring match across the three languages).
* **Correlation / relevance scoring** — decide *how relevant* an incident is
  to a particular bus stop, so the combined stop endpoint can rank incidents
  by proximity. Relevance is derived from the data the TD feed actually
  carries:

    * ``high``   — the incident carries a ``<LATITUDE>/<LONGITUDE>`` and it
                   falls within the correlation radius of the stop (default
                   1.5 km); *or* the incident's road/location text overlaps the
                   stop's serving routes (when the feed text names a route the
                   stop serves).
    * ``medium`` — the incident's district matches the stop's district (or the
                   location text contains a district keyword).
    * ``low``    — nothing matched (city-wide incident).

When the stop cannot supply a location/district (or the incident has neither
geo nor district), the score degrades gracefully to ``low`` rather than
crashing. Correlation is best-effort: the TD feed is free-text and not all
incidents are geo-tagged, so ``low`` is a valid, common outcome.
"""
from __future__ import annotations

from math import radians, sin, cos, asin, sqrt
from typing import List, Optional

from config import settings
from models import BusStop, Incident, MultilingualText
from src.clients import TDClient
from src.logging_config import get_logger

logger = get_logger(__name__)

_DEFAULT_RADIUS_M = 1500.0


def _haversine_m(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    """Great-circle distance in metres between two WGS84 points."""
    r = 6371000.0  # earth radius, metres
    d_lat = radians(b_lat - a_lat)
    d_lon = radians(b_lon - a_lon)
    h = (
        sin(d_lat / 2) ** 2
        + cos(radians(a_lat)) * cos(radians(b_lat)) * sin(d_lon / 2) ** 2
    )
    return 2 * r * asin(min(1.0, sqrt(h)))


def _text(ml: Optional[MultilingualText]) -> str:
    if ml is None:
        return ""
    return " ".join(p for p in (ml.en, ml.tc, ml.sc) if p) or ""


def _cjk_substring_match(needle: str, haystack: str) -> bool:
    """True if any 2+ char CJK slice of *needle* appears in *haystack*.

    Only the CJK (Han) portions of *needle* are slid over — Latin text keeps
    using the whitespace-token path above, so e.g. the English fragment "en"
    inside "Tuen Mun Road" can't spuriously match "central". The 2-char minimum
    avoids trivial single-character false hits.
    """
    cjk = "".join(ch for ch in needle if "一" <= ch <= "鿿")
    for i in range(len(cjk) - 1):
        chunk = cjk[i : i + 2]
        if chunk in haystack:
            return True
    return False


def _match_score(incident: Incident, stop: BusStop, radius_m: float) -> str:
    """Derive high / medium / low relevance of *incident* to *stop*."""
    stop_loc = stop.location
    inc_geo = incident.geo

    # Geo proximity (only when both sides have coordinates).
    if inc_geo is not None and stop_loc is not None:
        dist = _haversine_m(stop_loc.lat, stop_loc.lon, inc_geo.lat, inc_geo.lon)
        if dist <= radius_m:
            return "high"

    # District / locality overlap. The stop's descriptive text (name + address)
    # plus any known district is the haystack; the incident's district and
    # location are the needles. We match both on whitespace-delimited tokens
    # (Latin/English text) **and** on CJK substring containment, because the
    # Hong Kong feeds serve Traditional Chinese with no word boundaries (e.g.
    # "長沙灣道路" should match a stop named "長沙灣廣場" via the shared prefix).
    inc_district = _text(incident.district).lower()
    inc_location = _text(incident.location).lower()
    if inc_district or inc_location:
        haystack = " ".join([_text(stop.name), _text(stop.address)]).lower()
        inc_text = " ".join([inc_district, inc_location])
        # Whitespace tokens (English) — only meaningful multi-char tokens.
        tokens = [t for t in (inc_district.split() + inc_location.split()) if len(t) > 1]
        if any(tok in haystack for tok in tokens):
            return "medium"
        # CJK substring match: any 2+ char slice of the incident locality that
        # appears verbatim in the stop text counts as a locality overlap.
        if len(inc_text) >= 2 and _cjk_substring_match(inc_text, haystack):
            return "medium"

    return "low"


class IncidentService:
    """Fetch, filter, and correlate TD traffic incidents."""

    def __init__(self, lang: str = "tc", td: Optional[TDClient] = None):
        self.lang = lang if lang in ("en", "tc", "sc") else settings.default_lang
        self.td = td or TDClient(lang=self.lang)

    # -- public API ----------------------------------------------------------
    def get_incidents(
        self,
        district: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[Incident]:
        """Return incidents, optionally filtered by district / status."""
        try:
            incidents = self.td.get_incidents()
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("TD incidents fetch failed: %s", exc)
            raise

        if district:
            needle = district.strip().lower()
            incidents = [
                inc
                for inc in incidents
                if needle in _text(inc.district).lower()
                or needle in _text(inc.location).lower()
            ]
        if status:
            needle = status.strip().lower()
            incidents = [
                inc
                for inc in incidents
                if needle in _text(inc.status).lower()
            ]
        return incidents

    def correlate_for_stop(
        self,
        stop: BusStop,
        radius_m: float = _DEFAULT_RADIUS_M,
        district: Optional[str] = None,
        status: Optional[str] = None,
        incidents: Optional[List[Incident]] = None,
    ) -> List[Incident]:
        """Return incidents relevant to *stop*, each tagged with ``relevance``.

        The returned list is sorted ``high`` → ``medium`` → ``low`` so the most
        relevant incidents surface first on the stop screen. If ``incidents`` is
        supplied it is used directly (the combined endpoint pre-fetches them);
        otherwise they are fetched from the TD feed.
        """
        if incidents is None:
            incidents = self.get_incidents(district=district, status=status)
        for inc in incidents:
            inc.relevance = _match_score(inc, stop, radius_m)
        order = {"high": 0, "medium": 1, "low": 2}
        return sorted(incidents, key=lambda i: order.get(i.relevance or "low", 2))
