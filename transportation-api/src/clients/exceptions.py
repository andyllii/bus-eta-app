"""Typed exceptions raised by the upstream (Hong Kong open-data) clients.

Having a small exception hierarchy lets the aggregation layer distinguish
*retryable* failures (rate limiting, transient network/timeout) from
*permanent* ones (auth missing / rejected, 4xx). The combined endpoint stays
fail-soft, but typed errors make logs and the ``Error`` envelope far more
useful than a bare ``HTTPError``.

The providers themselves are currently keyless public feeds (KMB
``data.etabus.gov.hk``, Citybus ``rt.data.gov.hk``, HKO ``data.weather.gov.hk``,
TD ``td.gov.hk``). We still model the auth/rate-limit cases because:

* data.gov.hk publishes a keyed api.data.gov tier (HTTP ``X-Api-Key`` header,
  1,000 req/hour default) that operators may move to, and the shared client
  must degrade cleanly if a key is rejected or exhausted;
* the same client code is reused by future keyed feeds, so the contract is
  settled now rather than retrofitted later.
"""

from __future__ import annotations


class UpstreamError(Exception):
    """Base class for every error raised while talking to an upstream feed."""

    #: ``True`` => safe to retry (transient). ``False`` => permanent.
    retryable: bool = False

    def __init__(self, message: str, *, provider: str | None = None, status_code: int | None = None):
        self.provider = provider
        self.status_code = status_code
        super().__init__(message)


class UpstreamAuthError(UpstreamError):
    """Authentication to an upstream feed failed (missing/invalid key, 401/403).

    Permanent for a given configuration: retrying without fixing the key will
    keep failing, so :attr:`retryable` is ``False``.
    """

    retryable = False


class UpstreamRateLimitError(UpstreamError):
    """Upstream returned 429, or our local outbound limiter blocked the call.

    Retryable: the condition clears on its own (after the rate window resets or
    a short backoff). Carries ``retry_after`` seconds when known.
    """

    retryable = True

    def __init__(self, message: str, *, provider: str | None = None, retry_after: float | None = None):
        self.retry_after = retry_after
        super().__init__(message, provider=provider, status_code=429)


class UpstreamTimeoutError(UpstreamError):
    """The upstream feed did not respond within ``settings.request_timeout``."""

    retryable = True


class UpstreamConnectionError(UpstreamError):
    """Network-level failure (DNS, refused, reset) talking to the upstream."""

    retryable = True


class UpstreamServerError(UpstreamError):
    """Upstream returned 5xx. Transient — safe to retry with backoff."""

    retryable = True
