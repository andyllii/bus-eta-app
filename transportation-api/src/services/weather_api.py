"""Dedicated HKO weather endpoint service with endpoint-level caching.

This module backs the ``/api/v1/weather/hk`` endpoint. It wraps
:class:`src.clients.hko.HKOClient` and adds a *cross-request* TTL cache that
persists for the lifetime of the process (unlike the HKOClient's own short
in-memory cache, which is rebuilt whenever the route constructs a fresh client
per request).

The cache:
  * Keyed by the requested language (``en`` / ``tc`` / ``sc``) plus whether the
    optional 9-day forecast was requested, so each variant is cached
    independently.
  * Set from ``settings.cache_ttl_weather_api`` (default 10 minutes) to stay
    well under HKO rate limits while keeping data fresh.
  * Stores a *serialisable copy* of the payload so a later mutation of the
    returned model (e.g. attaching a forecast) can't poison the cached entry.

Fail-soft policy follows the existing endpoint contract: a missing current
weather feed yields ``None`` (surfaced as a 5xx ``UPSTREAM_ERROR`` by the
route), while warnings/forecast sub-feeds degrade to empty/omitted.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from config import settings
from models import Weather, WeatherWarning
from src.cache import TTLCache
from src.clients import HKOClient
from src.logging_config import get_logger

logger = get_logger(__name__)


class WeatherApiService:
    """Fetches + caches HKO weather for the ``/api/v1/weather/hk`` endpoint."""

    def __init__(self, cache_ttl: Optional[float] = None):
        self.cache_ttl = (
            cache_ttl if cache_ttl is not None else settings.cache_ttl_weather_api
        )
        self._cache = TTLCache(default_ttl=self.cache_ttl)

    # -- public API ----------------------------------------------------------
    def get_weather(
        self, lang: str = "en", include_forecast: bool = False
    ) -> Optional[Weather]:
        """Return the current HKO weather for Hong Kong, served from cache.

        The cached payload is deep-copied before any per-request enrichment
        (forecast attachment), so the stored entry is never mutated. Returns
        ``None`` when the core current-weather feed is unavailable.
        """
        cache_key = self._cache_key(lang, include_forecast)
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.debug("weather api cache hit (lang=%s, forecast=%s)", lang, include_forecast)
            # Return a copy so forecast attachment below can't mutate the cache.
            return cached.model_copy(deep=True)

        client = HKOClient(lang=lang)
        weather = client.get_current_weather()
        if weather is None:
            logger.error("HKO current weather feed unavailable (lang=%s)", lang)
            return None

        if include_forecast:
            fcast = client.get_9day_forecast()
            if fcast is not None:
                from models import ForecastDay

                weather.forecast = [ForecastDay(**d) for d in fcast if isinstance(d, dict)]

        # Persist a deep copy so the cache is insulated from later mutations.
        self._cache.set(cache_key, weather.model_copy(deep=True), ttl=self.cache_ttl)
        return weather

    def get_warnings(self, lang: str = "en") -> List[WeatherWarning]:
        """Return the currently active HKO weather warnings (cached)."""
        cache_key = self._cache_key(lang, "warnings")
        cached = self._cache.get(cache_key)
        if cached is not None:
            return [w.model_copy(deep=True) for w in cached]
        client = HKOClient(lang=lang)
        warnings = client.get_weather_warnings()
        self._cache.set(cache_key, list(warnings), ttl=self.cache_ttl)
        return warnings

    def clear_cache(self) -> None:
        self._cache.clear()

    # -- helpers --------------------------------------------------------------
    @staticmethod
    def _cache_key(lang: str, include_forecast) -> str:
        return f"weather:hk:{lang}:{include_forecast}"
