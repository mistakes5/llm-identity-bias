"""
Sliding-window-log rate limiter.
Thread-safe. Uses monotonic clock to avoid system-clock jumps.
"""
from __future__ import annotations
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque


@dataclass
class RateLimiter:
    """Allows at most `limit` requests per `window` seconds, per key."""

    limit: int
    window: float  # seconds

    _buckets: dict[str | None, Deque[float]] = field(default_factory=dict, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def is_allowed(self, key: str | None = None) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._get_bucket(key)
            self._evict_expired(bucket, now)
            if len(bucket) < self.limit:
                bucket.append(now)
                return True
            return False

    def remaining(self, key: str | None = None) -> int:
        now = time.monotonic()
        with self._lock:
            bucket = self._get_bucket(key)
            self._evict_expired(bucket, now)
            return max(0, self.limit - len(bucket))

    def reset_after(self, key: str | None = None) -> float:
        """Seconds until the oldest in-window request expires."""
        now = time.monotonic()
        with self._lock:
            bucket = self._get_bucket(key)
            self._evict_expired(bucket, now)
            return max(0.0, bucket[0] + self.window - now) if bucket else 0.0

    def timestamps(self, key: str | None = None) -> list[float]:
        """Snapshot of active timestamps (monotonic clock)."""
        now = time.monotonic()
        with self._lock:
            bucket = self._get_bucket(key)
            self._evict_expired(bucket, now)
            return list(bucket)

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key in self._buckets:
                self._buckets[key].clear()

    def _get_bucket(self, key: str | None) -> Deque[float]:
        if key not in self._buckets:
            self._buckets[key] = deque()
        return self._buckets[key]

    def _evict_expired(self, bucket: Deque[float], now: float) -> None:
        # TODO: implement sliding-window eviction
        # Remove timestamps from the left that are older than (now - self.window).
        # The deque is oldest-first, so popleft() until the front is within the window.
        raise NotImplementedError

def _evict_expired(self, bucket: Deque[float], now: float) -> None:
    cutoff = now - self.window
    while bucket and bucket[0] <= cutoff:
        bucket.popleft()

rl = RateLimiter(limit=3, window=1.0)
print([rl.is_allowed("user-1") for _ in range(5)])
# → [True, True, True, False, False]
print(rl.remaining("user-1"))  # → 0
print(rl.reset_after("user-1"))  # → ~0.9s