"""A tiny in-process TTL cache.

Avoids a hard Redis dependency for local/dev runs while still preventing
redundant network calls within a request batch. If REDIS_URL is set you can
swap this out later — the interface is intentionally minimal.
"""
from __future__ import annotations

import time
from threading import Lock
from typing import Any, Callable


class TTLCache:
    def __init__(self, ttl_seconds: int = 900) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}
        self._lock = Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            hit = self._store.get(key)
            if not hit:
                return None
            expires_at, value = hit
            if time.monotonic() > expires_at:
                self._store.pop(key, None)
                return None
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = (time.monotonic() + self._ttl, value)

    def get_or_set(self, key: str, producer: Callable[[], Any]) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached
        value = producer()
        self.set(key, value)
        return value
