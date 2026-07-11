"""Hong Kong Observatory (HKO) OpenData weather client.

Fetches current weather conditions, active warnings, and the 9-day forecast
from the HKO ``weatherAPI`` OpenData endpoint, then transforms the provider's
raw payloads into the canonical :class:`models.Weather` / :class:`models.WeatherWarning`
schemas used by the rest of the API.

Real HKO OpenData behaviour (verified against the live endpoint during build):
  * Every request needs ``rformat=json`` or the API returns an HTML error page.
  * ``dataType=rhrread``    -> current temp / humidity / icon / warning messages.
  * ``dataType=warnsum``    -> currently *active* warnings (code + localised name
    + issue/update times). This is the authoritative "are there any warnings"
    source; ``warningInfo`` returns an empty/absent ``details`` array when
    nothing is in force, so it alone would hide active warnings.
  * ``dataType=warningInfo`` -> full warning statement text (indexed by code).
  * ``dataType=fnd``        -> 9-day forecast (optional enrichment).

The ``lang`` parameter drives the language of the raw feeds (en / tc / sc).
Warning *titles* are localised via a small static map so a single request can
populate the full ``{en, tc, sc}`` title on each warning regardless of which
language the feed returned.

All methods are **fail-soft**: a provider error (network, timeout, parse) is
logged and yields ``None`` / ``[]`` rather than raising, so a partial HKO
outage never takes down the whole combined endpoint. The client subclasses
:class:`src.clients.base.BaseClient` for shared TTL caching + HTTP stack.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from config import settings
from models import Weather, WeatherWarning, MultilingualText
from src.clients.base import BaseClient


# ---------------------------------------------------------------------------
# Severity classification & multilingual warning titles
# ---------------------------------------------------------------------------
# HKO warning codes -> severity bucket (none / amber / red / black / warning).
# "warning" is the catch-all for signals that don't use a colour (typhoon
# signals, heat/cold, monsoon, tsunami, etc.).
_SEVERITY_BY_CODE = {
    # Rainstorm signals (colour-coded)
    "WRAINA": "amber", "WRAINR": "red", "WRAINB": "black",
    # Landslip (colour-coded)
    "WL": "amber", "WLR": "red", "WLB": "black",
    # Thunderstorm
    "WTCSGN": "warning",
    # Typhoon / wind signals (numbered 1/3/8/9/10)
    "WTC": "warning", "W1": "warning", "W3": "warning",
    "W8NE": "warning", "W8NW": "warning", "W8SE": "warning", "W8SW": "warning",
    "W9": "warning", "W10": "warning",
    # Special / other
    "WFROST": "warning", "WFIRE": "warning", "WColdt": "warning",
    "WHOT": "warning", "WMON": "warning", "WTMW": "warning", "WTS": "warning",
    "WFN": "warning", "WTH": "warning", "WCON": "warning", "WTFN": "warning",
}

# HKO weather-icon codes -> multilingual description of conditions.
# Source of truth: HKO "Weather Icons" reference (verified July 2026):
#   EN  https://www.hko.gov.hk/textonly/v2/explain/wxicon_e.htm
#   SC  https://www.hko.gov.hk/textonly/v2/explain/wxicon_sc.htm
# The rhrread feed returns only integer icon codes (e.g. 50 = "Sunny"),
# so we map them to a short condition string here. A single request
# frequently returns several codes (day/night + special); we keep the
# first human label as the canonical "description".
_WEATHER_ICON_DESC: Dict[str, Dict[str, str]] = {
    # --- Sun / cloud with possible showers (daytime) ---
    "50": {"en": "Sunny", "tc": "陽光充沛", "sc": "阳光充沛"},
    "51": {"en": "Sunny Periods", "tc": "間有陽光", "sc": "间有阳光"},
    "52": {"en": "Sunny Intervals", "tc": "短暫陽光", "sc": "短暂阳光"},
    "53": {"en": "Sunny Periods with A Few Showers", "tc": "間有陽光幾陣驟雨", "sc": "间有阳光几阵骤雨"},
    "54": {"en": "Sunny Intervals with Showers", "tc": "短暫陽光有驟雨", "sc": "短暂阳光有骤雨"},
    # --- Cloud / rain / thunder (daytime) ---
    "60": {"en": "Cloudy", "tc": "多雲", "sc": "多云"},
    "61": {"en": "Overcast", "tc": "密雲", "sc": "密云"},
    "62": {"en": "Light Rain", "tc": "微雨", "sc": "微雨"},
    "63": {"en": "Rain", "tc": "雨", "sc": "雨"},
    "64": {"en": "Heavy Rain", "tc": "大雨", "sc": "大雨"},
    "65": {"en": "Thunderstorms", "tc": "雷暴", "sc": "雷暴"},
    # --- Night-time icons (lunar-month / night only) ---
    "70": {"en": "Fine (night, 1st of Lunar Month)", "tc": "天色良好(只在農曆第一日晚間使用)", "sc": "天色良好(只在农曆第一日晚间使用)"},
    "71": {"en": "Fine (night, 2nd-6th of Lunar Month)", "tc": "天色良好(只在農曆第二日至第六日晚間使用)", "sc": "天色良好(只在农曆第二日至第六日晚间使用)"},
    "72": {"en": "Fine (night, 7th-13th of Lunar Month)", "tc": "天色良好(只在農曆第七日至第十三日晚間使用)", "sc": "天色良好(只在农曆第七日至第十三日晚间使用)"},
    "73": {"en": "Fine (night, 14th-17th of Lunar Month)", "tc": "天色良好(只在農曆第十四日至第十七日晚間使用)", "sc": "天色良好(只在农曆第十四日至第十七日晚间使用)"},
    "74": {"en": "Fine (night, 18th-24th of Lunar Month)", "tc": "天色良好(只在農曆第十八日至第二十四日晚間使用)", "sc": "天色良好(只在农曆第十八日至第二十四日晚间使用)"},
    "75": {"en": "Fine (night, 25th-30th of Lunar Month)", "tc": "天色良好(只在農曆第二十五日至第三十日晚間使用)", "sc": "天色良好(只在农曆第二十五日至第三十日晚间使用)"},
    "76": {"en": "Mainly Cloudy (night)", "tc": "大致多雲(只在晚間使用)", "sc": "大致多云(只在晚间使用)"},
    "77": {"en": "Mainly Fine (night)", "tc": "天色大致良好(只在晚間使用)", "sc": "天色大致良好(只在晚间使用)"},
    # --- Wind / humidity / visibility ---
    "80": {"en": "Windy", "tc": "大風", "sc": "大风"},
    "81": {"en": "Dry", "tc": "乾燥", "sc": "乾燥"},
    "82": {"en": "Humid", "tc": "潮濕", "sc": "潮湿"},
    "83": {"en": "Fog", "tc": "霧", "sc": "雾"},
    "84": {"en": "Mist", "tc": "薄霧", "sc": "薄雾"},
    "85": {"en": "Haze", "tc": "煙霞", "sc": "烟霞"},
    # --- Temperature ---
    "90": {"en": "Hot", "tc": "熱", "sc": "热"},
    "91": {"en": "Warm", "tc": "暖", "sc": "暖"},
    "92": {"en": "Cool", "tc": "涼", "sc": "凉"},
    "93": {"en": "Cold", "tc": "冷", "sc": "冷"},
}


def _description_for(icons: List[int], lang: str) -> Optional[str]:
    """Resolve a human-readable condition description from HKO icon codes.

    Picks the first icon that has a known mapping (icons are ordered by the
    feed, usually day-sky first) and returns its label in the requested
    language. Returns ``None`` when no icons are present or none are known.
    """
    for code in icons or []:
        mapped = _WEATHER_ICON_DESC.get(str(code))
        if mapped:
            return mapped.get(lang, mapped["en"])
    return None


# HKO warning codes -> multilingual display titles.
# Source: HKO Open Data API documentation warning codes.
_WARNING_TITLES: Dict[str, Dict[str, str]] = {
    "WRAINA": {"en": "Amber Rainstorm Warning Signal", "tc": "黃色暴雨警告信號", "sc": "黄色暴雨警告信号"},
    "WRAINR": {"en": "Red Rainstorm Warning Signal", "tc": "紅色暴雨警告信號", "sc": "红色暴雨警告信号"},
    "WRAINB": {"en": "Black Rainstorm Warning Signal", "tc": "黑色暴雨警告信號", "sc": "黑色暴雨警告信号"},
    "WL": {"en": "Amber Landslip Warning", "tc": "黃色山泥傾瀉警告", "sc": "黄色山泥倾泻警告"},
    "WLR": {"en": "Red Landslip Warning", "tc": "紅色山泥傾瀉警告", "sc": "红色山泥倾泻警告"},
    "WLB": {"en": "Black Landslip Warning", "tc": "黑色山泥傾瀉警告", "sc": "黑色山泥倾泻警告"},
    "WTCSGN": {"en": "Thunderstorm Warning", "tc": "雷暴警告", "sc": "雷暴警告"},
    "WTC": {"en": "Tropical Cyclone Warning", "tc": "熱帶氣旋警告", "sc": "热带气旋警告"},
    "W1": {"en": "Standby Signal, No. 1", "tc": "一號戒備信號", "sc": "一号戒备信号"},
    "W3": {"en": "Strong Wind Signal, No. 3", "tc": "三號強風信號", "sc": "三号强风信号"},
    "W8NE": {"en": "North-east Gale or Storm Signal, No. 8", "tc": "八號東北烈風或暴風信號", "sc": "八号东北烈风或暴风信号"},
    "W8NW": {"en": "North-west Gale or Storm Signal, No. 8", "tc": "八號西北烈風或暴風信號", "sc": "八号西北烈风或暴风信号"},
    "W8SE": {"en": "South-east Gale or Storm Signal, No. 8", "tc": "八號東南烈風或暴風信號", "sc": "八号东南烈风或暴风信号"},
    "W8SW": {"en": "South-west Gale or Storm Signal, No. 8", "tc": "八號西南烈風或暴風信號", "sc": "八号西南烈风或暴风信号"},
    "W9": {"en": "Increasing Gale or Storm Signal, No. 9", "tc": "九號烈風或暴風加強信號", "sc": "九号烈风或暴风加强信号"},
    "W10": {"en": "Hurricane Signal, No. 10", "tc": "十號颶風信號", "sc": "十号飓风信号"},
    "WFROST": {"en": "Frost Warning", "tc": "霜凍警告", "sc": "霜冻警告"},
    "WFIRE": {"en": "Fire Danger Warning", "tc": "火災危險警告", "sc": "火灾危险警告"},
    "WColdt": {"en": "Cold Weather Warning", "tc": "寒冷天氣警告", "sc": "寒冷天气警告"},
    "WHOT": {"en": "Very Hot Weather Warning", "tc": "酷熱天氣警告", "sc": "酷热天气警告"},
    "WMON": {"en": "Monsoon Signal", "tc": "季候風信號", "sc": "季候风信号"},
    "WTMW": {"en": "Tsunami Warning", "tc": "海嘯警告", "sc": "海啸警告"},
    "WTS": {"en": "Tsunami Information", "tc": "海嘯提示", "sc": "海啸提示"},
    "WFN": {"en": "Flooding in the Northern New Territories", "tc": "新界北部水浸特別報告", "sc": "新界北部水浸特别报告"},
    "WTH": {"en": "Very Hot Weather Information", "tc": "酷熱天氣特別提示", "sc": "酷热天气特别提示"},
    "WCON": {"en": "Cold Weather Information", "tc": "寒冷天氣特別提示", "sc": "寒冷天气特别提示"},
    "WTFN": {"en": "Thunderstorm Information", "tc": "雷暴特別提示", "sc": "雷暴特别提示"},
}


def _severity_for(code: str) -> str:
    return _SEVERITY_BY_CODE.get(code, "warning")


def _title_for(code: str, fed_name: Optional[str], lang: str) -> MultilingualText:
    """Build a multilingual title for a warning.

    Prefer the static map (guarantees all three languages). Fall back to the
    name returned by the HKO ``warnsum`` feed if the code is unknown.
    """
    mapped = _WARNING_TITLES.get(code)
    if mapped:
        return MultilingualText(en=mapped["en"], tc=mapped["tc"], sc=mapped["sc"])
    name = fed_name or code
    if lang == "en":
        return MultilingualText(en=name)
    return MultilingualText(tc=name, sc=name)


def _parse_dt(value: Any) -> Optional[datetime]:
    """Parse an HKO timestamp (ISO-8601, usually +08:00) to an aware datetime."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Raw provider payload models (keyed by HKO field names)
# ---------------------------------------------------------------------------
class _RHRead(BaseModel):
    """Current regional weather (dataType=rhrread).

    ``updateTime`` / ``iconUpdateTime`` are kept loose (``Any``) so an
    unexpected timestamp string never aborts the *whole* payload parse — we
    coerce them to aware datetimes downstream via :func:`_parse_dt`, which
    returns ``None`` on a bad value. This keeps the transform fail-soft.
    """
    temperature: Dict[str, Any] = Field(default_factory=dict)
    humidity: Dict[str, Any] = Field(default_factory=dict)
    icon: List[int] = Field(default_factory=list)
    icon_update_time: Optional[Any] = Field(None, alias="iconUpdateTime")
    update_time: Optional[Any] = Field(None, alias="updateTime")
    warning_message: List[str] = Field(default_factory=list, alias="warningMessage")


class _WarnSum(BaseModel):
    """Active warning summary (dataType=warnsum). Keyed by warning code."""
    model_config = {"extra": "allow"}

    @property
    def active(self) -> List[Dict[str, Any]]:
        out = []
        for body in self.__pydantic_extra__.values():
            if isinstance(body, dict) and "code" in body:
                out.append(body)
        return out


class _WarningInfo(BaseModel):
    """Full warning statements (dataType=warningInfo)."""
    details: List[Dict[str, Any]] = Field(default_factory=list)


class HKOClient(BaseClient):
    """Client for the HKO weatherAPI OpenData endpoint (cached)."""

    provider = "hko"

    def __init__(self, lang: str = "tc", base_url: Optional[str] = None, timeout: Optional[float] = None,
                 api_key: Optional[str] = None, rate_limit: Optional[float] = None,
                 rate_burst: Optional[float] = None, max_retries: Optional[int] = None):
        super().__init__(cache_ttl=settings.cache_ttl_weather, timeout=timeout,
                         api_key=api_key, rate_limit=rate_limit, rate_burst=rate_burst,
                         max_retries=max_retries)
        self.lang = lang if lang in ("en", "tc", "sc") else settings.default_lang
        self.base_url = base_url or settings.hko_base_url

    # --- low level ---------------------------------------------------------
    def _fetch_data(self, data_type: str) -> Optional[Dict[str, Any]]:
        params = {"dataType": data_type, "lang": self.lang, "rformat": "json"}
        try:
            return self._get_json(self.base_url, params=params)
        except Exception as exc:
            self.logger.error("HKO %s fetch failed: %s", data_type, exc)
            return None

    # --- public: current weather ------------------------------------------
    def get_current_weather(self) -> Optional[Weather]:
        """Fetch current weather + warnings -> canonical Weather (fail-soft).

        Returns ``None`` only if the core rhrread feed fails. A failure of the
        warnings sub-feed yields a warning populated with whatever could be
        recovered (e.g. titles from the static map).
        """
        data = self._fetch_data("rhrread")
        if not data:
            return None
        try:
            rh = _RHRead.model_validate(data)
        except Exception as exc:  # pydantic validation edge cases
            self.logger.error("Failed to parse HKO rhrread payload: %s", exc)
            return None

        temp_value = temp_place = temp_unit = None
        # The HKO feed labels the Hong Kong Observatory station in the
        # response language; match both the English and Chinese names so the
        # canonical reading is used regardless of the requested `lang`.
        for row in rh.temperature.get("data", []):
            if row.get("place") in ("香港天文台", "Hong Kong Observatory"):
                temp_value, temp_place, temp_unit = row.get("value"), row.get("place"), row.get("unit")
                break
        if temp_value is None and rh.temperature.get("data"):
            first = rh.temperature["data"][0]
            temp_value, temp_place, temp_unit = first.get("value"), first.get("place"), first.get("unit")

        humidity_value = humidity_unit = None
        for row in rh.humidity.get("data", []):
            humidity_value, humidity_unit = row.get("value"), row.get("unit")
            break

        temperature = {"place": temp_place, "value": temp_value, "unit": temp_unit} if temp_value is not None else None
        humidity = ({"value": humidity_value, "unit": (humidity_unit or "percent")} if humidity_value is not None else None)
        description = _description_for(rh.icon, self.lang)

        return Weather(
            temperature=temperature,
            description=description,
            humidity=humidity,
            icon=rh.icon,
            update_time=_parse_dt(rh.update_time),
            warnings=self.get_weather_warnings(),
        )

    # --- public: active warnings ------------------------------------------
    def get_weather_warnings(self) -> List[WeatherWarning]:
        """Return currently active warnings as canonical WeatherWarning objects.

        Combines ``warnsum`` (active codes + issue/update times, localised
        names) with ``warningInfo`` (statement text). Fail-soft: any sub-feed
        error is logged and skipped.
        """
        summary = self._fetch_data("warnsum")
        if not summary:
            return []
        try:
            warn_sum = _WarnSum.model_validate(summary)
        except Exception as exc:
            self.logger.error("Failed to parse HKO warnsum payload: %s", exc)
            return []

        statements: Dict[str, str] = {}
        info = self._fetch_data("warningInfo")
        if info:
            try:
                warn_info = _WarningInfo.model_validate(info)
                for detail in warn_info.details:
                    code = detail.get("warningStatementCode") or detail.get("code")
                    contents = detail.get("contents")
                    if code and contents:
                        statements[code] = " ".join(contents) if isinstance(contents, list) else str(contents)
            except Exception as exc:
                self.logger.error("Failed to parse HKO warningInfo payload: %s", exc)

        result: List[WeatherWarning] = []
        for body in warn_sum.active:
            code = body.get("code")
            if not code:
                continue
            result.append(
                WeatherWarning(
                    code=code,
                    title=_title_for(code, body.get("name"), self.lang),
                    severity=_severity_for(code),
                    contents=statements.get(code),
                    issue_time=_parse_dt(body.get("issueTime")),
                )
            )
        return result

    # --- public: 9-day forecast (optional) --------------------------------
    def get_9day_forecast(self) -> Optional[List[dict]]:
        """Best-effort 9-day forecast as a light list of day dicts (fail-soft)."""
        data = self._fetch_data("fnd")
        if not data:
            return None
        out = []
        for day in data.get("weatherForecast", []):
            out.append({
                "date": day.get("forecastDate"),
                "week": day.get("week"),
                "weather": day.get("forecastWeather"),
                "max_temp": day.get("forecastMaxtemp", {}).get("value"),
                "min_temp": day.get("forecastMintemp", {}).get("value"),
            })
        return out or None

    # --- backward-compatible aliases used by older call sites -------------
    def get_weather(self) -> Optional[Weather]:
        """Alias of :meth:`get_current_weather` (kept for route-compat)."""
        return self.get_current_weather()

    def get_weather_warnings_as_strings(self) -> List[str]:
        """Back-compat: active warnings as plain strings (legacy /eta shape)."""
        return [w.contents or (w.title.tc or "") for w in self.get_weather_warnings()]
