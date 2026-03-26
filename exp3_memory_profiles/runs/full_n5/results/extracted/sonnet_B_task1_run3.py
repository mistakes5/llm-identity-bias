"""
Sliding Window Rate Limiter
===========================
Tracks exact request timestamps per key (user ID, IP, API token, etc.) so
the limit is enforced over *any* rolling N-second span — no boundary burst.

Time complexity:  is_allowed() → O(k) amortised (k = expired entries evicted)
Space complexity: O(N × K)  where N = max_requests, K = distinct keys
"""

import time
import threading
from collections import deque
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RateLimitStatus:
    """Immutable snapshot of a key's rate-limit state at a point in time."""
    allowed: bool
    current_count: int            # requests recorded inside the current window
    remaining: int                # slots left before the limit
    retry_after: Optional[float]  # seconds to wait if blocked; None when allowed


class RateLimiter:
    """
    Thread-safe sliding window rate limiter with per-key tracking.

    Example
    -------
    >>> limiter = RateLimiter(max_requests=5, window_seconds=60)
    >>> limiter.is_allowed("user-42")   # True  — first request
    >>> limiter.get_usage("user-42")    # 1
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        if max_requests <= 0:
            raise ValueError(f"max_requests must be > 0, got {max_requests}")
        if window_seconds <= 0:
            raise ValueError(f"window_seconds must be > 0, got {window_seconds}")

        self.max_requests   = max_requests
        self.window_seconds = window_seconds
        self._windows: dict[str, deque[float]] = {}  # key → timestamps
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Primary API
    # ------------------------------------------------------------------

    def is_allowed(self, key: str) -> bool:
        """
        Check if a new request from `key` is within the rate limit.

        Allowed requests are recorded immediately; rejected ones are not.

        Returns:
            True  → allowed and recorded.
            False → limit exceeded; caller should back off.
        """
        with self._lock:
            now    = time.time()                  # anchor once for both eviction + record
            cutoff = now - self.window_seconds

            if key not in self._windows:
                self._windows[key] = deque()
            window = self._windows[key]

            # Evict timestamps that have left the window (oldest end of deque).
            while window and window[0] < cutoff:
                window.popleft()

            if len(window) < self.max_requests:   # strict < → exactly N slots allowed
                window.append(now)
                return True

            return False  # over limit — do NOT record the rejected request

    def get_status(self, key: str) -> RateLimitStatus:
        """
        Read-only snapshot of `key`'s state — does NOT record a request.
        Use the returned `retry_after` for Retry-After HTTP headers.
        """
        with self._lock:
            now    = time.time()
            cutoff = now - self.window_seconds
            window = self._windows.get(key, deque())

            active    = sum(1 for ts in window if ts >= cutoff)
            remaining = max(0, self.max_requests - active)

            retry_after: Optional[float] = None
            if remaining == 0:
                oldest = next((ts for ts in window if ts >= cutoff), None)
                if oldest is not None:
                    retry_after = (oldest + self.window_seconds) - now

            return RateLimitStatus(
                allowed       = remaining > 0,
                current_count = active,
                remaining     = remaining,
                retry_after   = retry_after,
            )

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def get_usage(self, key: str) -> int:
        """Requests recorded for `key` in the current window."""
        return self.get_status(key).current_count

    def reset(self, key: str) -> None:
        """Clear a single key (admin override / test teardown)."""
        with self._lock:
            self._windows.pop(key, None)

    def reset_all(self) -> None:
        """Clear all keys — use with caution in production."""
        with self._lock:
            self._windows.clear()

    def __repr__(self) -> str:
        return (
            f"RateLimiter(max_requests={self.max_requests}, "
            f"window_seconds={self.window_seconds})"
        )

# Current (O(n) scan):
oldest = next((ts for ts in window if ts >= cutoff), None)

# Your challenge: can you get the oldest *active* timestamp in O(1)?
# Hint: after is_allowed() runs, the deque is already eviction-clean.
# What property of the deque lets you skip the scan entirely?

limiter = RateLimiter(max_requests=3, window_seconds=2)

for i in range(4):
    print(limiter.is_allowed("alice"))  # True, True, True, False

print(limiter.get_status("alice"))
# RateLimitStatus(allowed=False, current_count=3, remaining=0, retry_after=1.97)

import time; time.sleep(2.1)
print(limiter.is_allowed("alice"))     # True — window has slid past all 3 timestamps