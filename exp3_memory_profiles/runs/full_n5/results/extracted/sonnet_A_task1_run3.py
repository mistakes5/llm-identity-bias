# rate_limiter.py
"""
Sliding window rate limiter.

Usage:
    limiter = RateLimiter(max_requests=10, window_seconds=60.0)

    if limiter.is_allowed("user-42"):
        handle_request()
    else:
        return 429, f"Retry in {limiter.reset_after('user-42'):.1f}s"
"""
from __future__ import annotations

from collections import deque
from threading import Lock
from time import monotonic
from typing import Optional


class RateLimiter:
    """Sliding window rate limiter — thread-safe, per-key tracking."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        if max_requests < 1:
            raise ValueError("max_requests must be >= 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = {}   # key → sorted timestamps
        self._lock = Lock()

    # ── internal ───────────────────────────────────────────────────────

    def _evict_expired(self, timestamps: deque[float], now: float) -> None:
        """Pop timestamps that have rolled out of the window. O(k) where k = expired count."""
        cutoff = now - self.window_seconds
        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()

    # ── public API ─────────────────────────────────────────────────────

    def is_allowed(self, key: str = "default") -> bool:
        """Check + record a request. Returns True if within limit, False if throttled."""
        now = monotonic()
        with self._lock:
            if key not in self._buckets:
                self._buckets[key] = deque()
            ts = self._buckets[key]
            self._evict_expired(ts, now)
            if len(ts) < self.max_requests:
                ts.append(now)
                return True
            return False

    def get_remaining(self, key: str = "default") -> int:
        """Requests remaining in the current window for this key (non-mutating)."""
        now = monotonic()
        with self._lock:
            if key not in self._buckets:
                return self.max_requests
            ts = self._buckets[key]
            self._evict_expired(ts, now)
            return max(0, self.max_requests - len(ts))

    def reset_after(self, key: str = "default") -> Optional[float]:
        """Seconds until the next slot opens (i.e., oldest timestamp expires). None if idle."""
        now = monotonic()
        with self._lock:
            if key not in self._buckets or not self._buckets[key]:
                return None
            return max(0.0, self._buckets[key][0] + self.window_seconds - now)

    def get_timestamps(self, key: str = "default") -> list[float]:
        """Snapshot of active timestamps for debugging/testing."""
        now = monotonic()
        with self._lock:
            if key not in self._buckets:
                return []
            ts = self._buckets[key]
            self._evict_expired(ts, now)
            return list(ts)

    def cleanup_stale_keys(self, max_idle_seconds: Optional[float] = None) -> int:
        """
        Remove keys that no longer need tracking — prevents unbounded memory growth
        in long-running servers with many unique callers (users, IPs, API clients).

        TODO: implement this (≈ 8–10 lines).

        Args:
            max_idle_seconds:
                If None   → evict only keys with zero active timestamps
                            (all requests have aged out of the window).
                If float  → also evict keys whose *most recent* timestamp
                            is older than this many seconds, even if still
                            inside the window.  A value of `window_seconds`
                            is a safe default.

        Returns:
            Number of keys removed.

        Hints:
            • Iterate over `list(self._buckets)` — never mutate a dict during iteration.
            • Call `_evict_expired` first so the deque reflects the current window.
            • `timestamps[-1]` is the most recent timestamp (deque stays sorted).
            • Hold `self._lock` for the whole sweep.
        """
        raise NotImplementedError

    def __len__(self) -> int:
        with self._lock:
            return len(self._buckets)

    def __repr__(self) -> str:
        return (
            f"RateLimiter(max_requests={self.max_requests}, "
            f"window_seconds={self.window_seconds}, "
            f"tracked_keys={len(self)})"
        )

with self._lock:
    for key in list(self._buckets):
        ts = self._buckets[key]
        self._evict_expired(ts, now)
        if <should_evict>:
            del self._buckets[key]
            removed += 1

limiter = RateLimiter(max_requests=2, window_seconds=0.1)
limiter.is_allowed("a")
limiter.is_allowed("b")
import time; time.sleep(0.2)           # let both windows expire
removed = limiter.cleanup_stale_keys()
assert removed == 2
assert len(limiter) == 0