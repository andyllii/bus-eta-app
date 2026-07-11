"""Transport Department (TD) traffic-news client — road incidents (XML feed).

The TD special-news traffic feed is XML::

    <list>
      <message>
        <INCIDENT_NUMBER>IN-26-04927</INCIDENT_NUMBER>
        <INCIDENT_HEADING_EN>...</INCIDENT_HEADING_EN>
        <INCIDENT_HEADING_CN>...</INCIDENT_HEADING_CN>
        <INCIDENT_DETAIL_EN>...</INCIDENT_DETAIL_EN>
        <INCIDENT_DETAIL_CN>...</INCIDENT_DETAIL_CN>
        <LOCATION_EN>...</LOCATION_EN>
        <LOCATION_CN>...</LOCATION_CN>
        <DISTRICT_EN>...</DISTRICT_EN>
        <DISTRICT_CN>...</DISTRICT_CN>
        <DIRECTION_EN>...</DIRECTION_EN>
        <DIRECTION_CN>...</DIRECTION_CN>
        <INCIDENT_STATUS_EN>NEW</INCIDENT_STATUS_EN>
        <INCIDENT_STATUS_CN>最新情況</INCIDENT_STATUS_CN>
        <ANNOUNCEMENT_DATE>2026-07-11T10:21:00</ANNOUNCEMENT_DATE>
        <NEAR_LANDMARK_EN>...</NEAR_LANDMARK_EN>
        <NEAR_LANDMARK_CN>...</NEAR_LANDMARK_CN>
        <BETWEEN_LANDMARK_EN>...</BETWEEN_LANDMARK_EN>
        <BETWEEN_LANDMARK_CN>...</BETWEEN_LANDMARK_CN>
        <ROAD_TYPE_EN>...</ROAD_TYPE_EN>
        <ROAD_TYPE_CN>...</ROAD_TYPE_CN>
        <ID>141824</ID>
        <CONTENT_EN>...</CONTENT_EN>
        <CONTENT_CN>...</CONTENT_CN>
        <LATITUDE>22.34</LATITUDE>
        <LONGITUDE>114.16</LONGITUDE>
      </message>
      ...
    </list>

The CN fields are Traditional Chinese in the TD feed (Hong Kong convention);
we expose them as ``tc`` and derive ``sc`` via the optional
:func:`_to_simplified` helper (falls back to tc when OpenCC is unavailable so
the model is always populated). Each incident maps to a canonical
:class:`Incident`.

The client captures *all* populated fields from the feed, including the
optional ``<ID>`` (message id), ``<CONTENT_EN/CN>`` (full narrative) and
``<LATITUDE>/<LONGITUDE>`` (geo-coordinate) — mapping them onto the
canonical ``source_id``, ``content`` and ``geo`` fields respectively. The
``announcement_date`` is normalised to the ``YYYY-MM-DD HH:MM`` shape the API
contract expects, regardless of whether the feed sends a bare ``YYYY-MM-DD
HH:MM`` string or an ISO-8601 ``YYYY-MM-DDTHH:MM:SS`` timestamp.
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Optional

import requests
from pydantic import BaseModel, Field

from config import settings
from models import GeoPoint, Incident, MultilingualText
from src.clients.base import BaseClient
from src.logging_config import get_logger

logger = get_logger(__name__)


def _to_simplified(tc_text: Optional[str]) -> Optional[str]:
    """Best-effort Traditional→Simplified (returns tc unchanged if unavailable)."""
    if not tc_text:
        return None
    try:
        from opencc import OpenCC  # type: ignore

        return OpenCC("t2s").convert(tc_text)
    except Exception:
        return tc_text


# Matches either ISO-8601 (2026-07-11T10:21:00) or the bare "YYYY-MM-DD HH:MM"
# form, with an optional timezone suffix (+08:00).
_ISO_DT = re.compile(
    r"^\s*(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?\s*"
    r"(?:(?:Z)|([+-]\d{2}:?\d{2}))?\s*$"
)


def normalize_announcement_date(raw: Optional[str]) -> Optional[str]:
    """Return ``YYYY-MM-DD HH:MM`` or None.

    Accepts the two shapes the TD feed has shipped historically (space- or
    ``T``-separated) plus an optional trailing ``+08:00`` / ``Z`` timezone.
    Falls back to the verbatim string when it cannot be parsed so we never
    silently drop a real value.
    """
    if not raw:
        return None
    raw = raw.strip()
    m = _ISO_DT.match(raw)
    if not m:
        return raw  # not a date we recognise; keep as-is
    year, month, day, hh, mm = m.group(1, 2, 3, 4, 5)
    return f"{year}-{month}-{day} {hh}:{mm}"


def parse_geo(lat_raw: Optional[str], lon_raw: Optional[str]) -> Optional[GeoPoint]:
    """Build a GeoPoint only when both coordinates are valid numbers."""
    if not lat_raw or not lon_raw:
        return None
    try:
        lat = float(lat_raw)
        lon = float(lon_raw)
    except (TypeError, ValueError):
        return None
    if not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
        return None
    return GeoPoint(lat=lat, lon=lon)


class TDRawIncident(BaseModel):
    incident_number: Optional[str] = Field(None, alias="INCIDENT_NUMBER")
    message_id: Optional[str] = Field(None, alias="ID")
    heading_en: Optional[str] = Field(None, alias="INCIDENT_HEADING_EN")
    heading_cn: Optional[str] = Field(None, alias="INCIDENT_HEADING_CN")
    detail_en: Optional[str] = Field(None, alias="INCIDENT_DETAIL_EN")
    detail_cn: Optional[str] = Field(None, alias="INCIDENT_DETAIL_CN")
    content_en: Optional[str] = Field(None, alias="CONTENT_EN")
    content_cn: Optional[str] = Field(None, alias="CONTENT_CN")
    location_en: Optional[str] = Field(None, alias="LOCATION_EN")
    location_cn: Optional[str] = Field(None, alias="LOCATION_CN")
    district_en: Optional[str] = Field(None, alias="DISTRICT_EN")
    district_cn: Optional[str] = Field(None, alias="DISTRICT_CN")
    direction_en: Optional[str] = Field(None, alias="DIRECTION_EN")
    direction_cn: Optional[str] = Field(None, alias="DIRECTION_CN")
    announcement_date: Optional[str] = Field(None, alias="ANNOUNCEMENT_DATE")
    status_en: Optional[str] = Field(None, alias="INCIDENT_STATUS_EN")
    status_cn: Optional[str] = Field(None, alias="INCIDENT_STATUS_CN")
    near_landmark_en: Optional[str] = Field(None, alias="NEAR_LANDMARK_EN")
    near_landmark_cn: Optional[str] = Field(None, alias="NEAR_LANDMARK_CN")
    between_landmark_en: Optional[str] = Field(None, alias="BETWEEN_LANDMARK_EN")
    between_landmark_cn: Optional[str] = Field(None, alias="BETWEEN_LANDMARK_CN")
    road_type_en: Optional[str] = Field(None, alias="ROAD_TYPE_EN")
    road_type_cn: Optional[str] = Field(None, alias="ROAD_TYPE_CN")
    latitude: Optional[str] = Field(None, alias="LATITUDE")
    longitude: Optional[str] = Field(None, alias="LONGITUDE")

    model_config = {"populate_by_name": True, "extra": "ignore"}

    def to_canonical(self) -> Incident:
        heading_tc = self.heading_cn
        detail_tc = self.detail_cn
        content_tc = self.content_cn
        location_tc = self.location_cn
        district_tc = self.district_cn
        status_tc = self.status_cn
        direction_tc = self.direction_cn
        road_type_tc = self.road_type_cn
        near_landmark_tc = self.near_landmark_cn
        return Incident(
            id=self.incident_number or f"TD-{self.message_id}",
            heading=MultilingualText(en=self.heading_en, tc=heading_tc, sc=_to_simplified(heading_tc)),
            detail=MultilingualText(en=self.detail_en, tc=detail_tc, sc=_to_simplified(detail_tc)),
            content=MultilingualText(en=self.content_en, tc=content_tc, sc=_to_simplified(content_tc)),
            location=MultilingualText(en=self.location_en, tc=location_tc, sc=_to_simplified(location_tc)),
            district=MultilingualText(en=self.district_en, tc=district_tc, sc=_to_simplified(district_tc)),
            direction=MultilingualText(en=self.direction_en, tc=direction_tc, sc=_to_simplified(direction_tc)),
            road_type=MultilingualText(en=self.road_type_en, tc=road_type_tc, sc=_to_simplified(road_type_tc)),
            near_landmark=MultilingualText(en=self.near_landmark_en, tc=near_landmark_tc, sc=_to_simplified(near_landmark_tc)),
            status=MultilingualText(en=self.status_en, tc=status_tc, sc=_to_simplified(status_tc)),
            announcement_date=normalize_announcement_date(self.announcement_date),
            source_id=self.message_id,
            geo=parse_geo(self.latitude, self.longitude),
        )

    @staticmethod
    def from_element(message: "ET.Element") -> "TDRawIncident":
        """Build a raw model from a ``<message>`` XML element (skip empty tags)."""
        data = {}
        for child in message:
            text = (child.text or "").strip()
            if text:  # TD marks absent fields as empty self-closing tags
                data[child.tag] = text
        return TDRawIncident.model_validate(data)


class TDClient(BaseClient):
    """Live Transport Department traffic-incident client (XML feed)."""

    provider = "td"

    def __init__(self, lang: str = "tc", base_url: Optional[str] = None, timeout: Optional[float] = None,
                 api_key: Optional[str] = None, rate_limit: Optional[float] = None,
                 rate_burst: Optional[float] = None, max_retries: Optional[int] = None):
        super().__init__(cache_ttl=settings.cache_ttl_incidents, timeout=timeout,
                         api_key=api_key, rate_limit=rate_limit, rate_burst=rate_burst,
                         max_retries=max_retries)
        if lang not in ("en", "tc", "sc"):
            raise ValueError("Language must be one of 'en', 'tc', or 'sc'.")
        self.lang = lang
        template = base_url or settings.td_base_url
        self.url = template.format(lang=lang)

    def get_incidents(self) -> List[Incident]:
        """Fetch + parse the TD feed into canonical :class:`Incident` models."""
        try:
            text = self._get_text(self.url)
        except requests.RequestException as exc:
            logger.error("TD traffic news fetch failed: %s", exc)
            raise
        except Exception as exc:
            logger.error("TD traffic news fetch failed: %s", exc)
            return []

        incidents: List[Incident] = []
        try:
            root = ET.fromstring(text)
        except ET.ParseError as exc:
            logger.error("Failed to parse TD XML: %s", exc)
            return incidents

        for message in root.findall("message"):
            try:
                incidents.append(TDRawIncident.from_element(message).to_canonical())
            except Exception as exc:
                logger.warning("Skipping malformed TD incident: %s", exc)
        return incidents
