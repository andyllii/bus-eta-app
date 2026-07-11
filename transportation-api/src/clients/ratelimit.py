"""Per-provider outbound rate limiter (leaky-bucket / token-bucket).

Why this exists
---------------
The upstream Hong Kong feeds are shared public resources. Some of them publish
explicit limits (e.g. data.gov.hk's keyed tier is 1,000 requests/hour by API
key). Even where a limit isn't documented, hammering a feed is poor citizenship
and invites IP-level throttling. So every provider client owns a small
:class:`RateLimiter` that paces outbound requests before they ever hit the
wire; if the bucket is empty we surface :class:`UpstreamRateLimitError` instead
of spamming the upstream.

The limiter is *local* (per process, per client instance) and thread-safe via a
lock. It is intentionally simple — a fixed refill rate with optional burst.
A multi-worker deployment would run several independent limiters (one per
worker), which still keeps aggregate traffic bounded because each worker is
already well under the upstream ceiling.

Design: token bucket
--------------------
* ``rate``      tokens per second (the sustained request rate).
* ``capacity``  max tokens the bucket can hold (allowed burst).
* A call consumes one token. If none are available, the wait needed to refill
  is computed and raised as an error (we don't block the request thread
  indefinitely — the caller's retry/backoff decides what to do).
"""

from __future__ import annotations

import threading
import time

from .exceptions import UpstreamRateLimitError


class RateLimiter:
    """Thread-safe token-bucket limiter for outbound upstream calls."""

    def __init__(self, rate: float = 10.0, capacity: float = 10.0, provider: str = "upstream"):
        # Guard against misconfiguration (rate <= 0 would mean never refill).
        self.rate = float(max(rate, 1e-6))
        self.capacity = float(max(capacity, 1.0))
        self.provider = provider
        self._tokens = self.capacity
        self._updated_at = time.monotonic()
        self._lock = threading.Lock()

    def _refill(self, now: float) -> None:
        elapsed = now - self._updated_at
        if elapsed <= 0:
            return
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._updated_at = now

    def acquire(self, tokens: float = 1.0) -> None:
        """Consume ``tokens`` or raise :class:`UpstreamRateLimitError`.

        Raises immediately if the bucket can't satisfy the request right now
        (computes how many seconds until one token frees up). Does not block.
        """
        if tokens > self.capacity:
            # Larger than any allowed burst — reject rather than deadlock.
            raise UpstreamRateLimitError(
                f"Request costs {tokens} tokens but bucket capacity is {self.capacity}",
                provider=self.provider,
            )
        with self._lock:
            now = time.monotonic()
            self._refill(now)
            if self._tokens >= tokens:
                self._tokens -= tokens
                return
            deficit = tokens - self._tokens
            wait = deficit / self.rate
        raise UpstreamRateLimitError(
            f"Outbound rate limit reached for '{self.provider}' "
            f"(need {tokens:.2f} token(s), have {self._tokens:.2f}); "
            f"retry after ~{wait:.1f}s",
            provider=self.provider,
            retry_after=max(wait, 0.0),
        )

    @property
    def available(self) -> float:
        """Current token count (snapshot, for diagnostics/logging)."""
        with self._lock:
            self._refill(time.monotonic())
            return self._tokens

    def __repr__(self) -> str:
        return (
            f"RateLimiter(provider={self.provider!r}, rate={self.rate:g}/s, "
            f"capacity={self.capacity:g}, tokens={self.available:.2f})"
        )
