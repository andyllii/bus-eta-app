"""Primary aggregation service behind ``GET /api/v1/eta``.

Given a bus ``route`` and ``stop`` this service fans out to the bus ETA,
HKO weather, and TD road-incident providers and returns a single
:class:`EtaAggregate` payload containing:

  1. the next few bus arrival times (filtered to the requested route),
  2. the current weather, and
  3. any traffic incidents that might affect the route (each tagged with a
     server-computed ``relevance`` of high / medium / low, sorted high-first).

The service is transport-agnostic (no FastAPI import) so it can be unit-tested
directly and reused by other routes.

Performance
-----------
* **Concurrent fetch** — the weather and incident providers are queried in
  parallel with a thread pool so the endpoint latency is bounded by the
  *slowest* upstream rather than the sum of them. (The ETA call is issued
  first, synchronously, because its resolved ``BusStop`` is needed to
  correlate incident relevance against the stop's real coordinates.)
* **Caching** — the whole assembled payload is memoised in a process-wide
  TTL cache (``settings.cache_ttl``) keyed by ``route|stop|lang|toggles``, so
  repeat requests for the same board (e.g. the frontend polling every few
  seconds) hit the cache instead of hammering the upstream feeds. Each
  upstream client also keeps its own short TTL cache inside
  :class:`src.clients.base.BaseClient`.

Resilience
----------
Each provider is queried inside its own try/except. When ``degrade`` is True
(the default), a *partial* provider failure degrades gracefully — the partial
payload is still returned and ``degraded`` is set to ``True`` so the UI can
show a "partial data" hint. A *missing stop/route* (no ETA returned at all) is
**not** degraded: it raises so the route can answer a clean 404. When
``degrade`` is False the first provider error propagates so the route can
answer 5xx.

A ``use_mock_data`` switch (default False) bypasses all providers and returns
the built-in mock so the endpoint works fully offline.
"""
from __future__ import annotations

import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional

from config import settings
from models import BusStop, EtaAggregate, EtaQuery, ETA, Incident, MultilingualText, Weather
from src.cache import TTLCache
from src.clients import CitybusClient, HKOClient, KMBClient, TDClient
from src.clients.exceptions import UpstreamError
from src.logging_config import get_logger
from src.services.incidents import IncidentService

logger = get_logger(__name__)


def _looks_like_kmb(stop_id: str) -> bool:
    """KMB stop ids are 16-char hex strings."""
    return len(stop_id) == 16 and all(c in "0123456789ABCDEFabcdef" for c in stop_id)


def _looks_like_citybus(stop_id: str) -> bool:
    """Citybus/NWFB stop ids are 6-digit numeric strings."""
    return stop_id.isdigit() and len(stop_id) == 6


class EtaAggregateService:
    """Builds :class:`EtaAggregate` payloads from live providers (concurrently)."""

    def __init__(
        self,
        lang: str = "tc",
        cache_ttl: Optional[float] = None,
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

        ttl = cache_ttl if cache_ttl is not None else settings.cache_ttl
        self._cache = TTLCache(default_ttl=ttl)

    # -- public API ----------------------------------------------------------
    def get_eta_aggregate(
        self,
        route: str,
        stop_id: str,
        lang: Optional[str] = None,
        include_weather: bool = True,
        include_incidents: bool = True,
        degrade: Optional[bool] = None,
    ) -> EtaAggregate:
        """Return the aggregated payload for ``route`` @ ``stop_id``.

        The whole result is served from a process-wide TTL cache keyed by
        ``route|stop_id|lang`` (+ the include_* toggles) so repeat requests for
        the same board are essentially free.
        """
        lang = lang or self.lang
        degrade = settings.degrade_on_upstream_error if degrade is None else degrade

        cache_key = self._cache_key(route, stop_id, lang, include_weather, include_incidents)
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug("eta_aggregate cache hit (route=%s, stop=%s)", route, stop_id)
            return cached

        payload = self._build(route, stop_id, lang, include_weather, include_incidents, degrade)
        self._cache.set(cache_key, payload, ttl=self._cache.default_ttl)
        return payload

    def clear_cache(self) -> None:
        self._cache.clear()

    # -- construction --------------------------------------------------------
    def _build(
        self,
        route: str,
        stop_id: str,
        lang: str,
        include_weather: bool,
        include_incidents: bool,
        degrade: bool,
    ) -> EtaAggregate:
        if settings.use_mock_data:
            return self._mock_aggregate(route, stop_id, lang, include_weather, include_incidents)

        # --- resolve stop + ETAs (operator decided by id shape) ------------
        stop: Optional[BusStop] = None
        etas: List[ETA] = []
        operator: Optional[str] = None
        eta_ok = True
        try:
            candidates: List = []
            if _looks_like_kmb(stop_id):
                candidates.append(self.kmb)
            if _looks_like_citybus(stop_id):
                candidates.append(self.citybus)
                candidates.append(self.citybus_nwfb)
            for client in candidates:
                # Resolve the stop once (cached in the client) to get real
                # coordinates for incident correlation.
                if stop is None:
                    try:
                        resolved = client.get_stop(stop_id)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("stop resolution failed for %s: %s", stop_id, exc)
                        resolved = None
                    if resolved is not None:
                        stop = resolved
                etas += client.get_stop_eta(stop_id) or []
            etas = [e for e in etas if e.route.upper() == route.upper()]
            if etas:
                operator = etas[0].co
        except Exception as exc:  # noqa: BLE001
            eta_ok = False
            logger.warning("ETA fetch failed for %s @ %s: %s", route, stop_id, exc)
            if not degrade:
                raise

        if not eta_ok or not etas:
            # The requested stop/route could not be resolved at all -> 404.
            # Degradation only covers *partial* failures (weather/incidents).
            raise UpstreamError(
                f"No ETA data for route {route} at stop {stop_id}.",
                provider="kmb",
            )

        # --- fetch weather + incidents concurrently ------------------------
        failed: List[str] = []
        weather: Optional[Weather] = None
        incidents: List[Incident] = []

        def _fetch_weather() -> Optional[Weather]:
            return self.hko.get_current_weather()

        def _fetch_incidents() -> List[Incident]:
            return self.td.get_incidents()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = {}
            if include_weather:
                futures["weather"] = pool.submit(_fetch_weather)
            if include_incidents:
                futures["incidents"] = pool.submit(_fetch_incidents)
            for fut in as_completed(futures.values()):
                # Resolve which logical block this future belongs to.
                name = next(k for k, v in futures.items() if v is fut)
                try:
                    result = fut.result()
                except Exception as exc:  # noqa: BLE001
                    if not degrade:
                        # Honour the degrade=false contract: surface the first
                        # partial failure as a typed error so the route can 5xx.
                        raise UpstreamError(
                            f"{name} provider failed: {exc}",
                            provider=name,
                        ) from exc
                    logger.warning("%s fetch failed: %s", name, exc)
                    failed.append(name)
                    continue
                if name == "weather":
                    weather = result
                else:
                    incidents = result or []

        # Compute per-route relevance so the UI can rank incidents by proximity
        # to the stop. Falls back gracefully when no real coordinate is known.
        # The correlation respects the same `degrade` policy: if the TD client
        # is unavailable it raises (or skips) consistently with the rest.
        if incidents and include_incidents:
            incidents = self._correlate(stop, incidents, degrade)

        degraded = bool(failed)
        query_time = datetime.datetime.now(datetime.timezone.utc)

        return EtaAggregate(
            query=EtaQuery(route=route, stop_id=stop_id, operator=operator, lang=lang),
            etas=etas,
            weather=weather if include_weather else None,
            incidents=incidents if include_incidents else [],
            query_time=query_time,
            degraded=degraded,
        )

    # -- relevance -----------------------------------------------------------
    def _correlate(self, stop: Optional[BusStop], incidents: List[Incident], degrade: bool) -> List[Incident]:
        """Tag incidents with route/stop relevance, sorted high-first.

        Reuses :class:`IncidentService.correlate_for_stop` so the geo + district
        + text correlation is identical to the ``/v1/bus-stops`` endpoint. When
        no real stop coordinate is available we still pass a minimal pseudo-stop
        carrying the route number as text, so incidents naming the route still
        surface (as medium) rather than dropping to low.
        """
        from models import GeoPoint

        if stop is None:
            stop = BusStop(
                id="route",
                name=MultilingualText(),
                location=GeoPoint(lat=0.0, lon=0.0),
            )
        service = IncidentService(td=self.td)
        try:
            return service.correlate_for_stop(stop, incidents=incidents)
        except Exception as exc:  # noqa: BLE001
            if degrade:
                logger.warning("Incident correlation failed, skipping: %s", exc)
                return incidents
            raise

    # -- offline mock --------------------------------------------------------
    def _mock_aggregate(
        self, route: str, stop_id: str, lang: str, include_weather: bool, include_incidents: bool
    ) -> EtaAggregate:
        from src.services.mock import _build_mock_combined  # local import avoids cycle

        # The sentinel id "DEADBEEF" is reserved to exercise the 404 path even
        # in mock mode (borrowed from the original combined-endpoint contract).
        if stop_id == "DEADBEEF":
            raise UpstreamError(
                f"No ETA data for route {route} at stop {stop_id}.",
                provider="kmb",
            )

        combined = _build_mock_combined()
        etas = [e for e in combined.etas if e.route.upper() == route.upper()]
        return EtaAggregate(
            query=EtaQuery(route=route, stop_id=stop_id, operator="KMB", lang=lang),
            etas=etas,
            weather=combined.weather if include_weather else None,
            incidents=combined.incidents if include_incidents else [],
            query_time=datetime.datetime.now(datetime.timezone.utc),
            degraded=False,
        )

    # -- helpers -------------------------------------------------------------
    def _cache_key(self, route: str, stop_id: str, lang: str, iw: bool, ii: bool) -> str:
        return f"eta_agg:{route.upper()}|{stop_id}|{lang}|w{iw}|i{ii}"
