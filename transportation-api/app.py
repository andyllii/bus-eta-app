"""
FastAPI application factory.

Builds the app, mounts the versioned routers, wires up logging, and registers
a global exception handler that always answers with the spec-shaped ``Error``
envelope (so a provider crash never leaks a raw 500 trace to clients).
Run with:  uvicorn app:app --host 0.0.0.0 --port 8000
(or via `python app.py` which uses the config-defined host/port).
"""
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

import uvicorn

from config import settings
from src.logging_config import get_logger
from models import Error
from routes import (
    eta_router,
    eta_aggregate_router,
    health_router,
    bus_stops_router,
    weather_router,
    weather_hk_router,
    incidents_router,
    search_router,
    weather_alias_router,
    incidents_alias_router,
    bus_stops_alias_router,
)

logger = get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="香港交通資訊聚合 API",
        description="一個整合九巴到站時間、天文台天氣同埋運輸署交通消息嘅API。",
        version=settings.app_version,
    )

    app.include_router(health_router)
    app.include_router(eta_router)
    app.include_router(eta_aggregate_router)
    app.include_router(bus_stops_router)
    app.include_router(weather_router)
    app.include_router(weather_hk_router)
    app.include_router(incidents_router)
    app.include_router(search_router)
    # Legacy /v1/... aliases (deprecated but kept for backward compatibility).
    app.include_router(weather_alias_router)
    app.include_router(incidents_alias_router)
    app.include_router(bus_stops_alias_router)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=Error(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred.",
                detail=str(exc),
            ).model_dump(mode="json"),
        )

    logger.info(
        "Initialized %s v%s (log_level=%s, use_mock_data=%s)",
        settings.app_name,
        settings.app_version,
        settings.log_level,
        settings.use_mock_data,
    )
    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run(app, host=settings.host, port=settings.port)
