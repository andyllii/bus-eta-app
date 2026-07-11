"""Citybus / NWFB ETA client (data.gov.hk real-time feed).

Citybus (CTB) and New World First Bus (NWFB) share the same
``rt.data.gov.hk/v2/transport/citybus`` API. Behaviour mirrors the KMB feed:

- Stop metadata ``/stop/{stopId}`` (6-digit id)::

      {"type":"Stop","version":"2.0","data":{
        "stop":"001027","name_tc":"中環 (港澳碼頭)","name_en":"Central (Macao Ferry)",
        "name_sc":"中环 (港澳码头)","lat":"22.288","long":"114.150",
        "data_timestamp":"2026-07-10T05:00:02+08:00"}}

- ETA ``/eta/{co}/{route}/{stopId}`` (co in CTB/NWFB)::

      {"type":"ETA","version":"2.0","data":[
        {"co":"CTB","route":"1","dir":"O","seq":1,"stop":"001027",
         "dest_tc":"...","dest_sc":"...","dest_en":"...",
         "eta_seq":1,"eta":"2026-07-11T03:01:02+08:00",
         "rmk_tc":"","rmk_sc":"","rmk_en":"",
         "data_timestamp":"2026-07-11T02:59:02+08:00"}, ...]}

Citybus stops use a *different* ID space from KMB (6-digit numeric vs KMB's
16-char hex), so a Citybus stop is only reachable when the caller supplies a
Citybus stop id. The combined endpoint resolves which client(s) to query.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from config import settings
from models import ETA as CanonicalETA
from models import BusStop, GeoPoint, MultilingualText
from src.clients.base import BaseClient, minutes_until


class CitybusETA(BaseModel):
    co: str
    route: str
    dir: str
    seq: int
    stop: str
    dest_tc: str = ""
    dest_sc: str = ""
    dest_en: str = ""
    eta_seq: int
    eta: Optional[datetime] = None
    rmk_tc: str = ""
    rmk_sc: str = ""
    rmk_en: str = ""
    data_timestamp: Optional[datetime] = None

    def to_canonical(self) -> CanonicalETA:
        dest = MultilingualText(tc=self.dest_tc or None, sc=self.dest_sc or None, en=self.dest_en or None)
        remark = MultilingualText(tc=self.rmk_tc or None, sc=self.rmk_sc or None, en=self.rmk_en or None)
        return CanonicalETA(
            co=self.co,
            route=self.route,
            direction=self.dir,
            service_type=1,
            seq=self.seq,
            dest=dest,
            eta_seq=self.eta_seq,
            eta=self.eta,
            minutes_remaining=minutes_until(self.eta),
            remark=None if remark.is_empty() else remark,
            data_timestamp=self.data_timestamp,
        )


class CitybusRawStop(BaseModel):
    stop: str
    name_tc: Optional[str] = None
    name_sc: Optional[str] = None
    name_en: Optional[str] = None
    lat: Optional[str] = None
    long: Optional[str] = None
    data_timestamp: Optional[datetime] = None


class CitybusClient(BaseClient):
    """Live Citybus/NWFB client (co = "CTB" or "NWFB")."""

    provider = "citybus"

    def __init__(
        self,
        co: str = "CTB",
        base_url: Optional[str] = None,
        timeout: Optional[float] = None,
        api_key: Optional[str] = None,
        rate_limit: Optional[float] = None,
        rate_burst: Optional[float] = None,
        max_retries: Optional[int] = None,
    ):
        super().__init__(cache_ttl=settings.cache_ttl_eta, timeout=timeout,
                         api_key=api_key, rate_limit=rate_limit, rate_burst=rate_burst,
                         max_retries=max_retries)
        self.co = co.upper()
        self.base_url = base_url or settings.citybus_base_url

    def get_stop(self, stop_id: str) -> Optional[BusStop]:
        payload = self._get_json(f"{self.base_url}/stop/{stop_id}")
        data = payload.get("data")
        if not data:
            return None
        raw = CitybusRawStop(**data)
        try:
            lat = float(raw.lat) if raw.lat is not None else 0.0
            lon = float(raw.long) if raw.long is not None else 0.0
        except (TypeError, ValueError):
            lat, lon = 0.0, 0.0
        return BusStop(
            id=raw.stop,
            name=MultilingualText(en=raw.name_en, tc=raw.name_tc, sc=raw.name_sc),
            location=GeoPoint(lat=lat, lon=lon),
            routes=[],
            data_timestamp=raw.data_timestamp,
        )

    @staticmethod
    def _parse_stop_eta(payload: Dict[str, Any]) -> List[CanonicalETA]:
        """Turn a raw Citybus ETA payload into canonical ETAs (skips bad rows)."""
        items = payload.get("data") or []
        etas: List[CanonicalETA] = []
        for item in items:
            try:
                etas.append(CitybusETA(**item).to_canonical())
            except Exception as exc:
                logger.warning("Skipping malformed Citybus ETA record: %s", exc)
        return etas

    def get_stop_eta(
        self,
        stop_id: str,
        route: Optional[str] = None,
        routes: Optional[List[str]] = None,
    ) -> List[CanonicalETA]:
        """ETA records for one Citybus/NWFB stop.

        The Citybus real-time feed **requires** a ``route`` on every ETA call —
        there is no "all ETAs for a stop" endpoint (unlike KMB's ``stop-eta``).
        So:
          * if ``route`` is given -> query that single route;
          * elif ``routes`` (a list) is given -> query each route and merge;
          * else -> query the configured ``settings.citybus_default_routes``
            (a best-effort common-route set) and merge. This keeps the combined
            endpoint useful even though the stop->route map isn't available.

        A route that happens to be empty (no buses scheduled) simply yields no
        records — it never 422s because the route segment is always present.
        """
        if route:
            query_routes = [route]
        elif routes:
            query_routes = list(routes)
        else:
            query_routes = list(settings.citybus_default_routes)

        etas: List[CanonicalETA] = []
        for r in query_routes:
            url = f"{self.base_url}/eta/{self.co}/{r}/{stop_id}"
            try:
                payload = self._get_json(url)
            except Exception as exc:
                # A 422 here would mean a genuinely invalid route id; skip it
                # rather than failing the whole stop.
                self.logger.warning("Citybus ETA fetch failed for %s/%s: %s", r, stop_id, exc)
                continue
            items = payload.get("data") or []
            etas.extend(self._parse_stop_eta(payload))
        return etas

    def get_route_eta(self, stop_id: str, route: str) -> List[CanonicalETA]:
        return self.get_stop_eta(stop_id, route=route)
