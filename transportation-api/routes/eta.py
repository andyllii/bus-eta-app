"""API route definitions."""
from fastapi import APIRouter, HTTPException, Query
import datetime

from config import settings
from models import EtaResponse, EtaItem
from src.clients import KMBClient, HKOClient, TDClient
from src.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter()
kmb_client = KMBClient()
hko_client = HKOClient(lang=settings.default_lang)
td_client = TDClient(lang=settings.default_lang)


@router.get("/eta", response_model=EtaResponse, summary="獲取巴士到站時間及相關天氣交通資訊")
def get_eta_with_alerts(
    route: str = Query(..., description="巴士路線, e.g., '1'"),
    stop_id: str = Query(..., description="巴士站ID, e.g., '946C74E30100FE80'"),
):
    """
    獲取指定巴士路線和站點的預計到站時間 (ETA)，並附上相關天氣警告和交通消息。
    """
    try:
        bus_etas = kmb_client.get_route_eta(stop_id, route)
    except Exception as e:
        logger.warning("KMB ETA fetch failed: %s", e)
        bus_etas = []

    try:
        weather_warnings = hko_client.get_weather_warnings_as_strings()
    except Exception as e:
        logger.warning("HKO warnings fetch failed: %s", e)
        weather_warnings = []

    try:
        traffic_incidents = td_client.get_incidents()
    except Exception as e:
        logger.warning("TD incidents fetch failed: %s", e)
        traffic_incidents = []

    eta_list = [
        EtaItem(
            route=eta.route,
            dest=eta.dest.tc or eta.dest.en or "",
            minutes_remaining=eta.minutes_remaining,
            eta_time=eta.eta.isoformat() if eta.eta else None,
            remark=(eta.remark.tc or eta.remark.en) if eta.remark else "",
        )
        for eta in bus_etas
    ]

    return EtaResponse(
        query_time=datetime.datetime.now(datetime.timezone.utc),
        bus_eta=eta_list,
        weather_warnings=weather_warnings,
        traffic_incidents=[inc.model_dump() for inc in traffic_incidents],
    )
