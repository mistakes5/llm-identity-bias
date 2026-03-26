"""
Sliding-window rate limiter.

Allows at most `max_requests` calls within any rolling `window_seconds` period.
Supports multiple independent keys (e.g. per-user, per-IP).
Thread-safe via per-key locks.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int      # slots left in the current window
    retry_after: float  # seconds until next slot opens (0.0 if allowed)
    request_count: int  # requests tracked right now for this key


class RateLimiter:
    """
    Sliding-window rate limiter.

    Args:
        max_requests:   Maximum requests allowed per window.
        window_seconds: Length of the rolling time window in seconds.
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        if max_requests <= 0:
            raise ValueError("max_requests must be a positive integer")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")

        self.max_requests = max_requests
        self.window_seconds = window_seconds

        self._timestamps: dict[str, deque[float]] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._global_lock = threading.Lock()  # only for creating new key entries

    # ── Public API ────────────────────────────────────────────────────

    def is_allowed(self, key: str = "default") -> RateLimitResult:
        """
        Check and record a request for *key*.

        Only records the timestamp when the request IS allowed,
        so rejected requests don't consume quota.
        """
        lock = self._get_lock(key)
        with lock:
            now = self._now()
            window = self._evict_expired(key, now)

            if len(window) < self.max_requests:
                window.append(now)
                return RateLimitResult(
                    allowed=True,
                    remaining=self.max_requests - len(window),
                    retry_after=0.0,
                    request_count=len(window),
                )
            else:
                retry_after = (window[0] + self.window_seconds) - now
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    retry_after=max(retry_after, 0.0),
                    request_count=len(window),
                )

    def peek(self, key: str = "default") -> RateLimitResult:
        """Inspect state for *key* WITHOUT recording a new request."""
        lock = self._get_lock(key)
        with lock:
            now = self._now()
            window = self._evict_expired(key, now)
            remaining = self.max_requests - len(window)
            retry_after = 0.0
            if remaining <= 0 and window:
                retry_after = max((window[0] + self.window_seconds) - now, 0.0)
            return RateLimitResult(
                allowed=remaining > 0,
                remaining=max(remaining, 0),
                retry_after=retry_after,
                request_count=len(window),
            )

    def reset(self, key: str = "default") -> None:
        """Clear all timestamps for *key* (e.g. after a successful auth flow)."""
        lock = self._get_lock(key)
        with lock:
            if key in self._timestamps:
                self._timestamps[key].clear()

    def timestamps(self, key: str = "default") -> list[float]:
        """Snapshot of active timestamps for *key* — useful for debugging."""
        lock = self._get_lock(key)
        with lock:
            window = self._evict_expired(key, self._now())
            return list(window)

    # ── Internals ─────────────────────────────────────────────────────

    def _get_lock(self, key: str) -> threading.Lock:
        """Return per-key lock, creating it atomically if absent."""
        if key not in self._locks:
            with self._global_lock:
                if key not in self._locks:      # double-checked locking
                    self._locks[key] = threading.Lock()
                    self._timestamps[key] = deque()
        return self._locks[key]

    def _evict_expired(self, key: str, now: float) -> deque[float]:
        """Drop timestamps outside the window. Caller must hold the key lock."""
        window = self._timestamps[key]
        cutoff = now - self.window_seconds
        while window and window[0] <= cutoff:
            window.popleft()
        return window

    @staticmethod
    def _now() -> float:
        return time.monotonic()  # immune to system clock adjustments

# 5 requests per 10-second window
limiter = RateLimiter(max_requests=5, window_seconds=10)

# Per-user rate limiting
result = limiter.is_allowed(key="user:alice")
if result.allowed:
    print(f"OK — {result.remaining} slots left")
else:
    print(f"Blocked — retry in {result.retry_after:.2f}s")

# Non-destructive status check
status = limiter.peek(key="user:alice")

# Reset after a successful payment / unlock
limiter.reset(key="user:alice")

# Debug: see raw timestamps
print(limiter.timestamps(key="user:alice"))

def cleanup(self) -> int:
    """
    Remove keys with no active timestamps.
    Returns the number of keys removed.
    """
    # TODO: your implementation here (~8-10 lines)
    # Consider:
    # - Do you need to acquire _global_lock or per-key locks, or both?
    # - What's the risk of evicting a key that's about to get a new request?
    # - Should you call this inline on every is_allowed(), or externally on a schedule?
    pass