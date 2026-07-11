"""Central configuration management for the transportation aggregation API.

Loads values from environment variables, with an optional .env file
populated via python-dotenv. All tunable knobs (host, port, log level,
external API base URLs, caching, mock fallback) live here so the rest of the
codebase reads ``settings.<attr>`` instead of touching ``os.environ`` directly.
"""
import os
from typing import Dict, List, Optional

from dotenv import load_dotenv

# Load .env from the project root (this file lives in <root>/config).
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))


class Settings:
    """Typed accessor for runtime configuration."""

    # --- Server ---
    app_name: str = os.getenv("APP_NAME", "transportation-api")
    app_version: str = os.getenv("APP_VERSION", "0.2.0")
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8000"))

    # --- Logging ---
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_dir: str = os.getenv("LOG_DIR", os.path.join(_PROJECT_ROOT, "logs"))

    # --- External data sources (public Hong Kong open-data endpoints) ---
    kmb_base_url: str = os.getenv(
        "KMB_BASE_URL", "https://data.etabus.gov.hk/v1/transport/kmb"
    )
    citybus_base_url: str = os.getenv(
        "CITYBUS_BASE_URL", "https://rt.data.gov.hk/v2/transport/citybus"
    )
    hko_base_url: str = os.getenv(
        "HKO_BASE_URL", "https://data.weather.gov.hk/weatherAPI/opendata/weather.php"
    )
    td_base_url: str = os.getenv(
        "TD_BASE_URL", "https://www.td.gov.hk/{lang}/special_news/trafficnews.xml"
    )

    # --- Request behaviour ---
    request_timeout: float = float(os.getenv("REQUEST_TIMEOUT", "10"))
    default_lang: str = os.getenv("DEFAULT_LANG", "tc")
    user_agent: str = os.getenv("USER_AGENT", "transportation-api/0.2 (+local)")

    # --- Upstream API authentication (optional, keyed tier) ---------------
    # The Hong Kong open-data feeds are public today (no key required), but
    # data.gov.hk publishes a keyed api.data.gov tier and operators may move
    # there. Set a key to have the shared client send it as an auth header.
    # Leave empty to call the feeds anonymously (current default behaviour).
    kmb_api_key: Optional[str] = os.getenv("KMB_API_KEY") or None
    citybus_api_key: Optional[str] = os.getenv("CITYBUS_API_KEY") or None
    hko_api_key: Optional[str] = os.getenv("HKO_API_KEY") or None
    td_api_key: Optional[str] = os.getenv("TD_API_KEY") or None
    # Header + scheme used when a key is present (api.data.gov uses the
    # standard ``Authorization: Bearer <key>`` form, or ``X-Api-Key: <key>``
    # by setting API_AUTH_HEADER=X-Api-Key and API_AUTH_SCHEME='').
    api_auth_header: str = os.getenv("API_AUTH_HEADER", "Authorization")
    api_auth_scheme: str = os.getenv("API_AUTH_SCHEME", "Bearer")

    # --- Outbound rate limiting (requests/second per provider) ------------
    # Paces our own calls so we never flood a shared public feed. One limiter
    # is shared per provider name across all client instances in the process.
    rate_limit_kmb: float = float(os.getenv("RATE_LIMIT_KMB", "20"))
    rate_limit_citybus: float = float(os.getenv("RATE_LIMIT_CITYBUS", "20"))
    rate_limit_hko: float = float(os.getenv("RATE_LIMIT_HKO", "10"))
    rate_limit_td: float = float(os.getenv("RATE_LIMIT_TD", "5"))
    # Burst capacity (tokens the bucket can hold); allows short spikes.
    rate_limit_burst: float = float(os.getenv("RATE_LIMIT_BURST", "10"))

    # --- Retry / backoff on transient upstream failures -------------------
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    retry_backoff_base: float = float(os.getenv("RETRY_BACKOFF_BASE", "0.25"))
    retry_backoff_max: float = float(os.getenv("RETRY_BACKOFF_MAX", "4.0"))

    # --- Caching (in-memory TTL, seconds) ---
    # Short TTLs: ETAs change minute-to-minute, weather/incidents less so.
    cache_ttl: float = float(os.getenv("CACHE_TTL", "30"))
    cache_ttl_eta: float = float(os.getenv("CACHE_TTL_ETA", "10"))
    cache_ttl_weather: float = float(os.getenv("CACHE_TTL_WEATHER", "30"))
    # Endpoint-level cache for the dedicated /api/v1/weather/hk endpoint. Long
    # enough (default 10 min) to shield HKO from rate-limiting, short enough to
    # stay fresh. Distinct from cache_ttl_weather (30s), which only applies
    # inside a single HKOClient instance and is therefore invisible across
    # requests when the route builds a fresh client per call.
    cache_ttl_weather_api: float = float(os.getenv("CACHE_TTL_WEATHER_API", "600"))
    cache_ttl_incidents: float = float(os.getenv("CACHE_TTL_INCIDENTS", "120"))

    # --- Citybus / NWFB route fan-out ------------------------------------
    # The Citybus real-time ETA feed requires a route id on every call (no
    # "all ETAs for a stop" endpoint). When the combined endpoint needs ETAs
    # for a Citybus stop but no specific route was requested, we fan out to
    # these common routes as a best-effort default. Override via env.
    citybus_default_routes: List[str] = [
        r.strip().upper()
        for r in os.getenv(
            "CITYBUS_DEFAULT_ROUTES",
            "1,6,7,12,25,90,970,973,A11,A12,A21,E11,N8,N11,N21,N23",
        ).split(",")
        if r.strip()
    ]
    # When true (default) and an upstream source fails, the combined endpoint
    # degrades gracefully (partial data) instead of erroring. When false, the
    # error propagates so clients get a 5xx. Also used for offline dev.
    degrade_on_upstream_error: bool = os.getenv(
        "DEGRADE_ON_UPSTREAM_ERROR", "true"
    ).lower() in ("1", "true", "yes", "on")

    # When true the endpoints bypass live providers entirely and serve the
    # built-in mock data set. Useful for demos/offline; off by default.
    use_mock_data: bool = os.getenv("USE_MOCK_DATA", "false").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

    @property
    def project_root(self) -> str:
        return _PROJECT_ROOT

    def as_dict(self) -> dict:
        d = {
            "app_name": self.app_name,
            "app_version": self.app_version,
            "host": self.host,
            "port": self.port,
            "log_level": self.log_level,
            "log_dir": self.log_dir,
            "kmb_base_url": self.kmb_base_url,
            "citybus_base_url": self.citybus_base_url,
            "hko_base_url": self.hko_base_url,
            "td_base_url": self.td_base_url,
            "request_timeout": self.request_timeout,
            "default_lang": self.default_lang,
            "cache_ttl": self.cache_ttl,
            "cache_ttl_eta": self.cache_ttl_eta,
            "cache_ttl_weather": self.cache_ttl_weather,
            "cache_ttl_weather_api": self.cache_ttl_weather_api,
            "cache_ttl_incidents": self.cache_ttl_incidents,
            "degrade_on_upstream_error": self.degrade_on_upstream_error,
            "use_mock_data": self.use_mock_data,
            # auth (never serialise the secret values themselves)
            "kmb_api_key_set": self.kmb_api_key is not None,
            "citybus_api_key_set": self.citybus_api_key is not None,
            "hko_api_key_set": self.hko_api_key is not None,
            "td_api_key_set": self.td_api_key is not None,
            "rate_limit_kmb": self.rate_limit_kmb,
            "rate_limit_citybus": self.rate_limit_citybus,
            "rate_limit_hko": self.rate_limit_hko,
            "rate_limit_td": self.rate_limit_td,
            "max_retries": self.max_retries,
        }
        return d


# Module-level singleton used across the app.
settings = Settings()
