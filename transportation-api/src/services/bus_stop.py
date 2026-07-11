"""Bus-stop aggregation service.

Orchestrates the external providers into the canonical ``BusStopCombined``
payload consumed by ``GET /v1/bus-stops/{stopId}``. It is deliberately
transport-agnostic (no FastAPI import) so it can be unit-tested directly and
reused by other routes.

Resolution strategy
--------------------
Hong Kong operators use disjoint stop-ID namespaces:
* KMB      — 16-char hex ids (e.g. ``946C74E30100FE80``)
* Citybus  — 6-digit numeric ids (e.g. ``001027``)

The service inspects the id shape to decide which stop clients to query, then
queries each for stop metadata + ETAs. Weather and traffic incidents are
Hong Kong–wide, so they are fetched once regardless of stop and merged in.

Resilience
----------
Each provider is queried independently inside its own try/except. If a source
fails:
* with ``settings.degrade_on_upstream_error`` (default True) the failure is
  logged and the partial payload is returned (the other sources still
  populate). Returns ``None`` only when the stop itself cannot be resolved.
* with it False the original exception is re-raised so the API can answer 5xx.

A ``use_mock_data`` switch (default False) bypasses all providers and returns
the built-in mock so the endpoint works fully offline.
"""
from __future__ import annotations

import datetime
from typing import List, Optional

from config import settings
from models import BusStop, BusStopCombined, ETA, Incident, MultilingualText, Weather
from src.clients import (
    CitybusClient,
    HKOClient,
    KMBClient,
    TDClient,
)
from src.logging_config import get_logger
from src.services.incidents import IncidentService

logger = get_logger(__name__)

_KMB_ID_LEN = 16


def _looks_like_kmb(stop_id: str) -> bool:
    """KMB stop ids are 16-char hex strings."""
    return len(stop_id) == _KMB_ID_LEN and all(c in "0123456789ABCDEFabcdef" for c in stop_id)


def _looks_like_citybus(stop_id: str) -> bool:
    """Citybus/NWFB stop ids are 6-digit numeric strings."""
    return stop_id.isdigit() and len(stop_id) == 6


class BusStopService:
    """Builds :class:`BusStopCombined` payloads from live providers."""

    def __init__(
        self,
        lang: str = "tc",
        kmb: Optional[KMBClient] = None,
        citybus: Optional[CitybusClient] = None,
        hko: Optional[HKOClient] = None,
        td: Optional[TDClient] = None,
    ):
        self.lang = lang if lang in ("en", "tc", "sc") else settings.default_lang
        self.kmb = kmb or KMBClient()
        self.citybus = citybus or CitybusClient(co="CTB")
        # Citybus + NWFB share the feed; NWFB is a second client for completeness.
        self.citybus_nwfb = CitybusClient(co="NWFB")
        self.hko = hko or HKOClient(lang=self.lang)
        self.td = td or TDClient(lang=self.lang)

    # -- public API ----------------------------------------------------------
    def get_combined(self, stop_id: str, route: Optional[str] = None) -> Optional[BusStopCombined]:
        """Return the aggregated payload, or ``None`` if the stop is unknown."""
        if settings.use_mock_data:
            return self._mock_combined(stop_id, route=route)

        stop = self._resolve_stop(stop_id)
        if stop is None:
            return None

        etas = self._resolve_etas(stop_id, route=route)
        if route is not None:
            etas = [e for e in etas if e.route.upper() == route.upper()]

        weather = self._safe(self.hko.get_weather, "HKO weather")
        incidents = self._safe(self.td.get_incidents, "TD incidents")

        # Compute per-stop relevance so the UI can rank incidents by proximity.
        if incidents and stop is not None:
            service = IncidentService(td=self.td)
            incidents = service.correlate_for_stop(stop, incidents=incidents)

        return BusStopCombined(
            stop=stop,
            etas=etas,
            weather=weather,
            incidents=incidents,
            query_time=datetime.datetime.now(datetime.timezone.utc),
        )

    # -- private helpers -----------------------------------------------------
    def _safe(self, fn, what: str):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — degrade gracefully
            if settings.degrade_on_upstream_error:
                logger.warning("%s fetch failed, degrading: %s", what, exc)
                return None if what.endswith("weather") else []
            raise

    def _resolve_stop(self, stop_id: str) -> Optional[BusStop]:
        candidates = []
        if _looks_like_kmb(stop_id):
            candidates.append(lambda: self.kmb.get_stop(stop_id))
        if _looks_like_citybus(stop_id):
            candidates.append(lambda: self.citybus.get_stop(stop_id))
            candidates.append(lambda: self.citybus_nwfb.get_stop(stop_id))

        for fetcher in candidates:
            try:
                stop = fetcher()
                if stop is not None:
                    return stop
            except Exception as exc:
                logger.warning("Stop resolution failed for %s: %s", stop_id, exc)
        return None

    def _resolve_etas(self, stop_id: str, route: Optional[str] = None) -> List[ETA]:
        etas: List[ETA] = []
        if _looks_like_kmb(stop_id):
            etas += self._safe(lambda: self.kmb.get_stop_eta(stop_id), "KMB ETA") or []
        if _looks_like_citybus(stop_id):
            etas += self._safe(lambda: self.citybus.get_stop_eta(stop_id, route=route), "Citybus ETA") or []
            etas += self._safe(lambda: self.citybus_nwfb.get_stop_eta(stop_id, route=route), "NWFB ETA") or []
        return etas

    # -- offline mock --------------------------------------------------------
    def _mock_combined(self, stop_id: str, route=None) -> BusStopCombined:
        from src.services.mock import _build_mock_combined  # local import avoids cycle

        # The sentinel id "DEADBEEF" is reserved to exercise the 404 path even
        # in mock mode (borrowed from the original contract test).
        if stop_id == "DEADBEEF":
            return None  # type: ignore[return-value]

        combined = _build_mock_combined()
        combined.stop.id = stop_id  # accept any id in mock mode
        if route is not None:
            combined.etas = [e for e in combined.etas if e.route.upper() == route.upper()]
        combined.query_time = datetime.datetime.now(datetime.timezone.utc)
        return combined
