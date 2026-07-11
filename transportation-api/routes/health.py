"""Health-check and meta routes."""
from fastapi import APIRouter
import datetime

from config import settings
from models import HealthStatus

router = APIRouter()


@router.get("/health", response_model=HealthStatus, tags=["health"])
def health_check():
    """Liveness/readiness probe — returns OK if the server is up."""
    return HealthStatus(
        status="ok",
        app_name=settings.app_name,
        app_version=settings.app_version,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )


@router.get("/", tags=["meta"])
def root():
    return {
        "app_name": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
        "health": "/health",
    }
