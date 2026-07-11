"""External data-source clients (KMB, Citybus, HKO, Transport Department)."""
from .base import BaseClient, minutes_until
from .kmb import KMBClient, KMBStopETA
from .citybus import CitybusClient, CitybusETA
from .hko import HKOClient
from .td import TDClient, TDRawIncident
from .exceptions import (
    UpstreamError,
    UpstreamAuthError,
    UpstreamRateLimitError,
    UpstreamServerError,
    UpstreamTimeoutError,
    UpstreamConnectionError,
)
from .ratelimit import RateLimiter

__all__ = [
    "BaseClient",
    "minutes_until",
    "KMBClient",
    "KMBStopETA",
    "CitybusClient",
    "CitybusETA",
    "HKOClient",
    "TDClient",
    "TDRawIncident",
    "UpstreamError",
    "UpstreamAuthError",
    "UpstreamRateLimitError",
    "UpstreamServerError",
    "UpstreamTimeoutError",
    "UpstreamConnectionError",
    "RateLimiter",
]
