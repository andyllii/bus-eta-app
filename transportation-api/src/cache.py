"""In-memory TTL cache used to shield upstream data sources from traffic.

A very small, dependency-free LRU-ish cache: entries expire after a per-entry
TTL (default taken from ``settings.cache_ttl``). It is process-local, which is
fine for a single-instance API server; a multi-worker deployment would share
load across workers and each worker keeps its own short-lived copy.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class _Entry:
    value: Any
    expires_at: float


class TTLCache:
    """Minimal thread-unsafe TTL cache keyed by string."""

    def __init__(self, default_ttl: float = 30.0):
        self.default_ttl = default_ttl
        self._store: Dict[str, _Entry] = {}

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.expires_at < time.monotonic():
            # Expired — drop it so it can be refetched.
            del self._store[key]
            return None
        return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        ttl = self.default_ttl if ttl is None else ttl
        self._store[key] = _Entry(value=value, expires_at=time.monotonic() + ttl)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)
