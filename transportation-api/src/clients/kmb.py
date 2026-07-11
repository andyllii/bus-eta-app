"""Kowloon Motor Bus (KMB) ETA client — reads live bus arrival times.

Uses the public KMB open data feed (data.etabus.gov.hk). The authenticated
"StopETA" shape is::

    {"type":"StopETA","version":"1.0",
     "generated_timestamp":"2026-07-11T02:56:31+08:00",
     "data":[
        {"co":"KMB","route":"1","dir":"O","service_type":1,"seq":8,
         "dest_tc":"...","dest_sc":"...","dest_en":"...",
         "eta_seq":1,"eta":null|"2026-07-11T02:59:31+08:00",
         "rmk_tc":"","rmk_sc":"","rmk_en":"",
         "data_timestamp":"2026-07-11T02:56:08+08:00"}, ...]}

``eta`` may be null (no predicted arrival, e.g. end of service) and the remark
fields may be empty strings. Both are normalised.

Stop metadata endpoint ``/stop/{id}``::

    {"type":"Stop","version":"1.0","generated_timestamp":"...",
     "data":{"stop":"...","name_en":"...","name_tc":"...","name_sc":"...",
             "lat":"22.33","long":"114.18"}}

Returns ``{"data":{}}`` (HTTP 200) for an unknown stop.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from config import settings
from models import ETA as CanonicalETA
from models import BusStop, GeoPoint, MultilingualText
from src.clients.base import BaseClient, minutes_until
from src.logging_config import get_logger

logger = get_logger(__name__)


class KMBStopETA(BaseModel):
    """Raw KMB StopETA record (provider field names)."""

    co: str
    route: str
    dir: str
    service_type: int = 1
    seq: int
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
            service_type=self.service_type,
            seq=self.seq,
            dest=dest,
            eta_seq=self.eta_seq,
            eta=self.eta,
            minutes_remaining=minutes_until(self.eta),
            remark=None if remark.is_empty() else remark,
            data_timestamp=self.data_timestamp,
        )


class KMBRawStop(BaseModel):
    stop: str
    name_en: Optional[str] = None
    name_tc: Optional[str] = None
    name_sc: Optional[str] = None
    lat: Optional[str] = None
    long: Optional[str] = None
    data_timestamp: Optional[datetime] = None


class KMBClient(BaseClient):
    """Live KMB client. ``get_stop()`` returns a canonical BusStop (or None),
    ``get_stop_eta()`` returns canonical ETAs for every route at the stop."""

    provider = "kmb"

    def __init__(self, base_url: Optional[str] = None, timeout: Optional[float] = None,
                 api_key: Optional[str] = None, rate_limit: Optional[float] = None,
                 rate_burst: Optional[float] = None, max_retries: Optional[int] = None):
        super().__init__(cache_ttl=settings.cache_ttl_eta, timeout=timeout,
                         api_key=api_key, rate_limit=rate_limit, rate_burst=rate_burst,
                         max_retries=max_retries)
        self.base_url = base_url or settings.kmb_base_url

    # -- stop metadata -------------------------------------------------------
    def get_stop(self, stop_id: str) -> Optional[BusStop]:
        payload = self._get_json(f"{self.base_url}/stop/{stop_id}")
        data = payload.get("data")
        if not data:
            return None
        raw = KMBRawStop(**data)
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

    # -- ETAs ----------------------------------------------------------------
    @staticmethod
    def _parse_stop_eta(payload: Dict[str, Any]) -> List[CanonicalETA]:
        """Turn a raw KMB StopETA payload into canonical ETAs (skips bad rows)."""
        items = payload.get("data") or []
        etas: List[CanonicalETA] = []
        for item in items:
            try:
                etas.append(KMBStopETA(**item).to_canonical())
            except Exception as exc:  # skip malformed records, keep the rest
                logger.warning("Skipping malformed KMB ETA record: %s", exc)
        return etas

    def get_stop_eta(self, stop_id: str) -> List[CanonicalETA]:
        payload = self._get_json(f"{self.base_url}/stop-eta/{stop_id}")
        return self._parse_stop_eta(payload)

    def get_route_eta(self, stop_id: str, route: str) -> List[CanonicalETA]:
        return [e for e in self.get_stop_eta(stop_id) if e.route.upper() == route.upper()]
