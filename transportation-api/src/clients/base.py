"""Base HTTP client with TTL caching, auth, rate limiting, and retry for the
external Hong Kong data sources (KMB, Citybus/NWFB, HKO, TD).

Every provider client subclasses :class:`BaseClient`, so they all share one
HTTP stack and one caching strategy. On top of caching this base layer adds
three production concerns the task calls out explicitly:

1. **API authentication** (optional). The live feeds are public today, but the
   shared client can attach an auth header when a key is configured
   (``settings.<provider>_api_key``). This keeps us ready for a keyed tier
   without changing per-provider code.

2. **Rate limiting** (outbound). A per-provider token bucket
   (:class:`src.clients.ratelimit.RateLimiter`) paces our own calls so we
   never flood a shared public feed. If the bucket is empty we raise
   :class:`UpstreamRateLimitError` rather than spamming the upstream.

3. **Error handling + retry**. Transient failures (connection errors, timeouts,
   HTTP 429/5xx, rate-limit) are retried with exponential backoff; permanent
   failures (auth rejected, HTTP 4xx) raise immediately as a typed
   :class:`UpstreamError` subclass. After retries are exhausted the typed error
   propagates to the caller, which decides whether to degrade gracefully
   (combined endpoint) or surface a 5xx.

A ``User-Agent`` is always sent because some Hong Kong government endpoints
reject requests with an empty UA.
"""

from __future__ import annotations

import hashlib
import json
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests

from config import settings
from src.cache import TTLCache
from src.clients.exceptions import (
    UpstreamAuthError,
    UpstreamConnectionError,
    UpstreamError,
    UpstreamRateLimitError,
    UpstreamServerError,
    UpstreamTimeoutError,
)
from src.clients.ratelimit import RateLimiter
from src.logging_config import get_logger

# One limiter per provider, shared across all client instances in the process.
_limiters: Dict[str, "RateLimiter"] = {}
_limiters_lock = __import__("threading").Lock()


def _get_limiter(provider: str, rate: float, capacity: float) -> "RateLimiter":
    with _limiters_lock:
        lim = _limiters.get(provider)
        if lim is None:
            lim = RateLimiter(rate=rate, capacity=capacity, provider=provider)
            _limiters[provider] = lim
        return lim


def minutes_until(dt: Optional[datetime]) -> Optional[int]:
    """Whole minutes from *now* (UTC) until ``dt``; ``None`` if ``dt`` is None.

    Returns ``0`` for times in the past so a "due" bus never shows negative
    minutes. Accepts both naive and timezone-aware datetimes (naive are
    treated as UTC).
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return max(0, int((dt - now).total_seconds() // 60))


class BaseClient:
    """Shared GET + TTL cache + auth + rate-limit + retry for provider clients.

    Subclasses pass a ``provider`` name (e.g. ``"kmb"``) so the right auth key,
    rate limit, and limiter are selected automatically.
    """

    #: Subclasses override; picks settings.<provider>_api_key + rate limit.
    provider: str = "upstream"

    def __init__(
        self,
        cache_ttl: Optional[float] = None,
        timeout: Optional[float] = None,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        rate_limit: Optional[float] = None,
        rate_burst: Optional[float] = None,
        max_retries: Optional[int] = None,
    ):
        self.provider = provider or self.provider
        self.timeout = timeout if timeout is not None else settings.request_timeout
        self.cache = TTLCache(default_ttl=cache_ttl if cache_ttl is not None else settings.cache_ttl)
        self.logger = get_logger(f"{self.__class__.__name__}[{self.provider}]")

        # --- auth ----------------------------------------------------------
        # Explicit api_key wins; otherwise fall back to settings.<provider>_api_key.
        self.api_key = api_key
        if self.api_key is None:
            self.api_key = getattr(settings, f"{self.provider}_api_key", None)
        self._auth_header = settings.api_auth_header
        self._auth_scheme = settings.api_auth_scheme

        # --- rate limiting ------------------------------------------------
        rl = rate_limit if rate_limit is not None else getattr(settings, f"rate_limit_{self.provider}", 10.0)
        burst = rate_burst if rate_burst is not None else settings.rate_limit_burst
        self.limiter = _get_limiter(self.provider, rate=rl, capacity=burst)

        # --- retry ---------------------------------------------------------
        self.max_retries = max_retries if max_retries is not None else settings.max_retries

    # -- public cache control ------------------------------------------------
    def invalidate_cache(self) -> None:
        self.cache.clear()

    # -- auth header ---------------------------------------------------------
    def _auth_headers(self) -> Dict[str, str]:
        if not self.api_key:
            return {}
        if self._auth_scheme:
            value = f"{self._auth_scheme} {self.api_key}"
        else:
            value = self.api_key
        return {self._auth_header: value}

    # -- low-level fetch with retry -----------------------------------------
    def _request(self, url: str, params: Optional[Dict[str, Any]] = None, as_text: bool = False) -> Any:
        """GET ``url`` with cache, rate-limit gating, auth, and retry/backoff.

        Returns parsed JSON (``as_text=False``) or raw text (``as_text=True``).
        Raises a typed :class:`UpstreamError` subclass on permanent failure or
        after retries are exhausted.
        """
        cache_key = self._cache_key(url, params)

        # 1. cache (skip on non-GET-like idempotent reads is irrelevant; all are GET)
        cached = self.cache.get(cache_key)
        if cached is not None:
            self.logger.debug("cache hit %s", url)
            return cached

        # 2. rate-limit gate (before spending a network call)
        self.limiter.acquire(1.0)

        last_exc: Optional[Exception] = None
        attempt = 0
        while attempt <= self.max_retries:
            try:
                headers = {"User-Agent": settings.user_agent}
                headers.update(self._auth_headers())
                try:
                    resp = requests.get(url, params=params, timeout=self.timeout, headers=headers)
                except Exception as exc:  # DNS/timeout/connection from requests
                    raise self._wrap_requests_error(exc, url, provider=self.provider)
                self._raise_for_status(resp)
                data = resp.text if as_text else resp.json()
                self.cache.set(cache_key, data, ttl=self._ttl_for(resp))
                return data
            except UpstreamRateLimitError:
                # Local bucket or upstream 429 — always retryable; re-raise to
                # let the caller's backoff (or our loop) handle it.
                raise
            except UpstreamAuthError:
                # Permanent — do not retry with the same (bad) key.
                raise
            except UpstreamError as exc:
                last_exc = exc
                if not exc.retryable or attempt >= self.max_retries:
                    break
                self._sleep_backoff(attempt)
            attempt += 1

        assert last_exc is not None
        raise last_exc

    def _get_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return self._request(url, params=params, as_text=False)

    def _get_text(self, url: str, params: Optional[Dict[str, Any]] = None) -> str:
        return self._request(url, params=params, as_text=True)

    # -- status / error translation ----------------------------------------
    def _raise_for_status(self, resp: "requests.Response") -> None:
        if resp.status_code < 400:
            return
        status = resp.status_code
        url = str(resp.url)
        if status in (401, 403):
            raise UpstreamAuthError(
                f"Upstream '{url}' rejected auth (HTTP {status}).",
                provider=self.provider,
                status_code=status,
            )
        if status == 429:
            retry_after = None
            ra = resp.headers.get("Retry-After")
            if ra:
                try:
                    retry_after = float(ra)
                except ValueError:
                    retry_after = None
            raise UpstreamRateLimitError(
                f"Upstream rate limit hit (HTTP 429) for '{url}'.",
                provider=self.provider,
                retry_after=retry_after,
            )
        if status >= 500:
            raise UpstreamServerError(
                f"Upstream server error (HTTP {status}) for '{url}'.",
                provider=self.provider,
                status_code=status,
            )
        # Other 4xx — permanent client error; surface with the real status.
        raise UpstreamError(
            f"Upstream client error (HTTP {status}) for '{url}'.",
            provider=self.provider,
            status_code=status,
        )

    # -- retry backoff -------------------------------------------------------
    def _sleep_backoff(self, attempt: int) -> None:
        base = settings.retry_backoff_base
        cap = settings.retry_backoff_max
        # exponential with full jitter
        sleep_for = min(cap, base * (2 ** attempt))
        sleep_for = sleep_for * random.uniform(0.5, 1.0)
        self.logger.warning(
            "Transient upstream error, backing off %.2fs before retry %d/%d",
            sleep_for, attempt + 1, self.max_retries,
        )
        time.sleep(sleep_for)

    # -- transport error mapping (wraps requests) ---------------------------
    @staticmethod
    def _wrap_requests_error(exc: Exception, url: str, provider: str = "upstream") -> UpstreamError:
        from requests.exceptions import Timeout, ConnectionError as ReqConnectionError

        if isinstance(exc, Timeout):
            return UpstreamTimeoutError(f"Upstream request timed out: {url}", provider=provider)
        if isinstance(exc, ReqConnectionError):
            return UpstreamConnectionError(f"Upstream connection failed: {url}", provider=provider)
        return UpstreamError(f"Upstream request failed: {exc}", provider=provider)

    # -- helpers -------------------------------------------------------------
    @staticmethod
    def _cache_key(url: str, params: Optional[Dict[str, Any]]) -> str:
        raw = url + "|" + json.dumps(params or {}, sort_keys=True, default=str)
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _ttl_for(resp: "requests.Response") -> Optional[float]:
        """Honour a ``Cache-Control: max-age`` header when present."""
        cc = resp.headers.get("Cache-Control", "")
        for part in cc.split(","):
            part = part.strip()
            if part.startswith("max-age="):
                try:
                    return float(part.split("=", 1)[1])
                except (ValueError, IndexError):
                    return None
        return None
