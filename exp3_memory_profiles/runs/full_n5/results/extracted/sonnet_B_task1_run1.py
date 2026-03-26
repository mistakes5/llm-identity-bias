# rate_limiter.py
"""
Sliding-window rate limiter.

Tracks individual request timestamps in a deque. On every check, expired
timestamps (older than `window_seconds`) are evicted from the left, so the
deque always represents the *active* window.

Thread-safe via a threading.Lock.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Optional


class RateLimiter:
    """Allow at most `max_requests` calls within a rolling `window_seconds` window."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        if max_requests <= 0:
            raise ValueError("max_requests must be a positive integer")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")

        self.max_requests = max_requests
        self.window_seconds = window_seconds

        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    def _evict_expired(self, now: float) -> None:
        """Remove timestamps outside the current window (call while lock is held)."""
        cutoff = now - self.window_seconds
        while self._timestamps and self._timestamps[0] <= cutoff:
            self._timestamps.popleft()

    # ------------------------------------------------------------------
    # Core method — YOUR TURN  ← implement this
    # ------------------------------------------------------------------

    def is_allowed(self, timestamp: Optional[float] = None) -> bool:
        """
        Check whether a new request is permitted right now.

        If allowed  → record it and return True.
        If denied   → do NOT record it, return False.

        Args:
            timestamp: Override current time (useful in tests).
                       Defaults to time.monotonic().
        """
        raise NotImplementedError("Implement is_allowed() — see guidance below")

    # ------------------------------------------------------------------
    # Convenience / introspection
    # ------------------------------------------------------------------

    def get_request_count(self, timestamp: Optional[float] = None) -> int:
        """Number of requests recorded in the current window."""
        now = timestamp if timestamp is not None else time.monotonic()
        with self._lock:
            self._evict_expired(now)
            return len(self._timestamps)

    def remaining(self, timestamp: Optional[float] = None) -> int:
        """How many more requests are allowed before the limit is hit."""
        return max(0, self.max_requests - self.get_request_count(timestamp))

    def retry_after(self, timestamp: Optional[float] = None) -> Optional[float]:
        """
        Seconds until the next slot opens. Returns None if a request is
        currently allowed (no wait needed).
        """
        now = timestamp if timestamp is not None else time.monotonic()
        with self._lock:
            self._evict_expired(now)
            if len(self._timestamps) < self.max_requests:
                return None
            return self._timestamps[0] + self.window_seconds - now

    def get_timestamps(self) -> list[float]:
        """Snapshot of active request timestamps (for debugging)."""
        with self._lock:
            return list(self._timestamps)

    def reset(self) -> None:
        """Clear all recorded timestamps."""
        with self._lock:
            self._timestamps.clear()

    def __repr__(self) -> str:
        return (
            f"RateLimiter(max_requests={self.max_requests}, "
            f"window_seconds={self.window_seconds})"
        )

def is_allowed(self, timestamp: Optional[float] = None) -> bool:
    now = timestamp if timestamp is not None else time.monotonic()
    with self._lock:
        # 1. Evict expired timestamps
        # 2. Check the count against self.max_requests
        # 3. If allowed: append `now` to self._timestamps, return True
        # 4. If denied:  return False (don't append)
        ...