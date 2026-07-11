"""Built-in mock data for offline / demo mode.

When ``settings.use_mock_data`` is enabled, the combined endpoint serves this
spec-conformant :class:`BusStopCombined` for any stop id instead of hitting
live providers. Kept as a standalone builder so tests can reuse it and the
route stays free of hardcoded test data.
"""
from __future__ import annotations

import datetime

from models import (
    BusStop,
    BusStopCombined,
    ETA,
    GeoPoint,
    Incident,
    MultilingualText,
    Weather,
    WeatherWarning,
)

_QUERY_TIME = datetime.datetime(2026, 7, 10, 8, 45, 0, tzinfo=datetime.timezone.utc)
_DATA_TS = datetime.datetime(2026, 7, 10, 8, 40, 0, tzinfo=datetime.timezone.utc)
_ETA_TS = datetime.datetime(2026, 7, 10, 8, 49, 0, tzinfo=datetime.timezone.utc)


def _build_mock_combined() -> BusStopCombined:
    stop = BusStop(
        id="946C74E30100FE80",
        name=MultilingualText(en="Cheung Sha Wan Plaza", tc="長沙灣廣場", sc="长沙湾广场"),
        location=GeoPoint(lat=22.333, lon=114.161),
        address=MultilingualText(en="Cheung Sha Wan Road, Kowloon", tc="九龍長沙灣道", sc="九龙长沙湾道"),
        routes=["1", "2", "6"],
        data_timestamp=_DATA_TS,
    )

    etas = [
        ETA(
            co="KMB", route="1", direction="O", service_type=1, seq=12,
            dest=MultilingualText(en="Central (Macao Ferry)", tc="中環（港澳碼頭）", sc="中环（港澳码头）"),
            eta_seq=1, eta=_ETA_TS, minutes_remaining=4,
            remark=MultilingualText(en="Scheduled", tc="預定", sc="预定"),
            data_timestamp=_DATA_TS,
        ),
        ETA(
            co="KMB", route="1", direction="O", service_type=1, seq=12,
            dest=MultilingualText(en="Central (Macao Ferry)", tc="中環（港澳碼頭）", sc="中环（港澳码头）"),
            eta_seq=2, eta=_ETA_TS + datetime.timedelta(minutes=11), minutes_remaining=15,
            remark=None, data_timestamp=_DATA_TS,
        ),
        ETA(
            co="KMB", route="2", direction="O", service_type=1, seq=8,
            dest=MultilingualText(en="West Kowloon Cultural District", tc="西九文化區", sc="西九文化区"),
            eta_seq=1, eta=_ETA_TS + datetime.timedelta(minutes=3), minutes_remaining=3,
            remark=MultilingualText(en="KMB staff on board", tc="九巴職員當值", sc="九巴职员当值"),
            data_timestamp=_DATA_TS,
        ),
    ]

    weather = Weather(
        description="Light Rain",
        temperature={"place": "Hong Kong Observatory", "value": 28, "unit": "C"},
        humidity={"value": 84, "unit": "%"},
        icon=[62],
        update_time=_DATA_TS,
        warnings=[
            WeatherWarning(
                code="WRAINA",
                title=MultilingualText(en="Amber Rainstorm Warning Signal", tc="黃色暴雨警告信號", sc="黄色暴雨警告信号"),
                severity="amber",
                contents="Amber Rainstorm Warning is in force. Rainfall exceeds 30 millimetres in an hour.",
                issue_time=_DATA_TS,
            )
        ],
        forecast=[{"date": "2026-07-11", "weather": "Rain", "max_temp": 30, "min_temp": 27}],
    )

    incidents = [
        Incident(
            id="TD20260710-00123",
            heading=MultilingualText(en="Road blocked due to accident", tc="因交通意外道路封閉", sc="因交通意外道路封闭"),
            detail=MultilingualText(en="One lane closed on Cheung Sha Wan Road.", tc="長沙灣道一條行車線封閉。", sc="长沙湾道一条行车线封闭。"),
            location=MultilingualText(en="Cheung Sha Wan Road", tc="長沙灣道", sc="长沙湾道"),
            district=MultilingualText(en="Sham Shui Po", tc="深水埗", sc="深水埗"),
            direction=None,
            road_type=MultilingualText(en="Road", tc="道路", sc="道路"),
            near_landmark=MultilingualText(en="Cheung Sha Wan Plaza", tc="長沙灣廣場", sc="长沙湾广场"),
            status=MultilingualText(en="ACTIVE", tc="生效中", sc="生效中"),
            announcement_date="2026-07-10 08:30",
            relevance="high",
        )
    ]

    return BusStopCombined(
        stop=stop, etas=etas, weather=weather, incidents=incidents, query_time=_QUERY_TIME
    )
