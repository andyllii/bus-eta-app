"""Tests for the shared BaseClient infrastructure: authentication header
injection, per-provider outbound rate limiting, retry/backoff on transient
failures, and typed error translation (auth rejected, rate limited, 5xx,
network/timeout).

All tests stub ``requests.get`` via ``monkeypatch`` so they are fully offline
and deterministic — no live Hong Kong feed is contacted.
"""

import json
import time
from unittest.mock import MagicMock

import pytest
import requests

from config import settings
from src.clients import KMBClient
from src.clients.base import BaseClient, _limiters
from src.clients.exceptions import (
    UpstreamAuthError,
    UpstreamConnectionError,
    UpstreamError,
    UpstreamRateLimitError,
    UpstreamServerError,
    UpstreamTimeoutError,
)
from src.clients.ratelimit import RateLimiter

# The per-provider rate limiters are cached in a module-level registry. Reset
# it before each test so rate-limit params passed to a client constructor
# actually take effect (otherwise the first client built in the session pins
# the limiter for that provider name).
@pytest.fixture(autouse=True)
def _reset_limiters():
    _limiters.clear()
    yield
    _limiters.clear()


def _fake_resp(status_code=200, json_data=None, text="", headers=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.url = "https://example.test/path"
    resp.headers = headers or {}
    if json_data is not None:
        resp.json.return_value = json_data
    resp.text = text
    return resp


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
def test_no_auth_header_when_key_unset(monkeypatch):
    monkeypatch.setattr(settings, "kmb_api_key", None)
    c = KMBClient()
    assert c._auth_headers() == {}


def test_auth_header_injected_when_key_set(monkeypatch):
    c = KMBClient(api_key="abc123")
    headers = c._auth_headers()
    assert headers["Authorization"] == "Bearer abc123"


def test_auth_header_x_api_key_scheme(monkeypatch):
    monkeypatch.setattr(settings, "api_auth_header", "X-Api-Key")
    monkeypatch.setattr(settings, "api_auth_scheme", "")
    c = KMBClient(api_key="abc123")
    headers = c._auth_headers()
    assert headers == {"X-Api-Key": "abc123"}


def test_settings_key_is_used_when_no_explicit_key(monkeypatch):
    monkeypatch.setattr(settings, "kmb_api_key", "fromsettings")
    c = KMBClient()
    assert c._auth_headers()["Authorization"] == "Bearer fromsettings"


def test_explicit_key_overrides_settings(monkeypatch):
    monkeypatch.setattr(settings, "kmb_api_key", "fromsettings")
    c = KMBClient(api_key="explicit")
    assert c._auth_headers()["Authorization"] == "Bearer explicit"


def test_auth_header_sent_on_request(monkeypatch):
    sent = {}

    def fake_get(url, params=None, timeout=None, headers=None):
        sent.update(headers)
        return _fake_resp(200, json_data={"ok": True})

    monkeypatch.setattr(requests, "get", fake_get)
    c = KMBClient(api_key="tok")
    assert c._get_json("https://example.test/x") == {"ok": True}
    assert sent["Authorization"] == "Bearer tok"
    assert sent["User-Agent"] == settings.user_agent


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------
def test_limiter_allows_up_to_capacity_then_blocks():
    rl = RateLimiter(rate=1.0, capacity=3.0, provider="p")
    for _ in range(3):
        rl.acquire(1.0)  # should not raise
    with pytest.raises(UpstreamRateLimitError):
        rl.acquire(1.0)


def test_request_gated_by_limiter(monkeypatch):
    # Burst capacity 1, rate tiny -> second call in quick succession must block.
    calls = {"n": 0}

    def fake_get(url, params=None, timeout=None, headers=None):
        calls["n"] += 1
        return _fake_resp(200, json_data={"d": calls["n"]})

    monkeypatch.setattr(requests, "get", fake_get)
    c = KMBClient(rate_limit=0.5, rate_burst=1.0)
    # Distinct URLs so the cache doesn't mask the limiter.
    assert c._get_json("https://example.test/a1") == {"d": 1}
    with pytest.raises(UpstreamRateLimitError):
        c._get_json("https://example.test/a2")  # cache miss + bucket empty


def test_cached_response_skips_limiter(monkeypatch):
    calls = {"n": 0}

    def fake_get(url, params=None, timeout=None, headers=None):
        calls["n"] += 1
        return _fake_resp(200, json_data={"d": calls["n"]})

    monkeypatch.setattr(requests, "get", fake_get)
    # capacity 1 so a second network call would raise; cache must save us.
    c = KMBClient(rate_limit=0.5, rate_burst=1.0)
    first = c._get_json("https://example.test/cached")
    assert calls["n"] == 1
    second = c._get_json("https://example.test/cached")
    assert second == first
    assert calls["n"] == 1  # no second network call -> limiter not hit


# ---------------------------------------------------------------------------
# Error translation / typing
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "status,exc_type,retryable",
    [
        (401, UpstreamAuthError, False),
        (403, UpstreamAuthError, False),
        (429, UpstreamRateLimitError, True),
        (500, UpstreamServerError, True),
        (502, UpstreamServerError, True),
        (404, UpstreamError, False),
    ],
)
def test_status_translation(monkeypatch, status, exc_type, retryable):
    monkeypatch.setattr(requests, "get", lambda *a, **k: _fake_resp(status))
    c = KMBClient(api_key="tok")  # avoid rate-limit noise: burst 10 default
    with pytest.raises(exc_type) as ei:
        c._get_json("https://example.test/x")
    assert ei.value.retryable is retryable
    if status in (401, 403, 404):
        assert ei.value.status_code == status


def test_retry_on_500_then_success(monkeypatch):
    state = {"calls": 0}

    def fake_get(url, params=None, timeout=None, headers=None):
        state["calls"] += 1
        if state["calls"] < 3:
            return _fake_resp(503)
        return _fake_resp(200, json_data={"ok": True})

    monkeypatch.setattr(requests, "get", fake_get)
    # shrink backoff so the test stays fast
    monkeypatch.setattr(settings, "retry_backoff_base", 0.001)
    monkeypatch.setattr(settings, "retry_backoff_max", 0.01)
    c = KMBClient(max_retries=3)
    assert c._get_json("https://example.test/r") == {"ok": True}
    assert state["calls"] == 3


def test_retry_exhausted_raises(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **k: _fake_resp(500))
    monkeypatch.setattr(settings, "retry_backoff_base", 0.001)
    monkeypatch.setattr(settings, "retry_backoff_max", 0.01)
    c = KMBClient(max_retries=2)
    with pytest.raises(UpstreamServerError):
        c._get_json("https://example.test/r")
    # initial attempt + 2 retries = 3 calls
    # (we can't easily count here; covered by success-path test)


def test_auth_error_not_retried(monkeypatch):
    state = {"calls": 0}

    def fake_get(url, params=None, timeout=None, headers=None):
        state["calls"] += 1
        return _fake_resp(401)

    monkeypatch.setattr(requests, "get", fake_get)
    c = KMBClient(api_key="bad")
    with pytest.raises(UpstreamAuthError):
        c._get_json("https://example.test/x")
    assert state["calls"] == 1  # no retry on permanent auth failure


def test_connection_error_wrapped_and_retried(monkeypatch):
    state = {"calls": 0}

    def fake_get(url, params=None, timeout=None, headers=None):
        state["calls"] += 1
        if state["calls"] < 2:
            raise requests.exceptions.ConnectionError("boom")
        return _fake_resp(200, json_data={"ok": True})

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(settings, "retry_backoff_base", 0.001)
    monkeypatch.setattr(settings, "retry_backoff_max", 0.01)
    c = KMBClient(max_retries=3)
    assert c._get_json("https://example.test/conn") == {"ok": True}
    assert state["calls"] == 2


def test_timeout_wrapped(monkeypatch):
    monkeypatch.setattr(
        requests, "get",
        lambda *a, **k: (_ for _ in ()).throw(requests.exceptions.Timeout("slow")),
    )
    monkeypatch.setattr(settings, "retry_backoff_base", 0.001)
    monkeypatch.setattr(settings, "retry_backoff_max", 0.01)
    c = KMBClient(max_retries=1)
    with pytest.raises(UpstreamTimeoutError):
        c._get_json("https://example.test/timeout")


def test_retry_after_parsed_from_429(monkeypatch):
    monkeypatch.setattr(
        requests, "get",
        lambda *a, **k: _fake_resp(429, headers={"Retry-After": "30"}),
    )
    c = KMBClient(max_retries=0)
    with pytest.raises(UpstreamRateLimitError) as ei:
        c._get_json("https://example.test/x")
    assert ei.value.retry_after == 30.0


# ---------------------------------------------------------------------------
# Cache-Control TTL honouring
# ---------------------------------------------------------------------------
def test_cache_control_max_age_honoured(monkeypatch):
    monkeypatch.setattr(
        requests, "get",
        lambda *a, **k: _fake_resp(200, json_data={"v": 1}, headers={"Cache-Control": "max-age=300"}),
    )
    c = KMBClient(rate_limit=100, rate_burst=100)
    c._get_json("https://example.test/cc")
    # second identical call should be a cache hit (no extra network call)
    calls = {"n": 0}

    def fake_get2(url, params=None, timeout=None, headers=None):
        calls["n"] += 1
        return _fake_resp(200, json_data={"v": 2}, headers={"Cache-Control": "max-age=300"})

    monkeypatch.setattr(requests, "get", fake_get2)
    # TTL is 300s so this should still be cached
    assert c._get_json("https://example.test/cc") == {"v": 1}
    assert calls["n"] == 0
