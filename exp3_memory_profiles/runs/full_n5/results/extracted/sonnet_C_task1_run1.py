# rate_limiter.py
import time
import threading
from collections import deque


class RateLimiter:
    """
    Sliding-window rate limiter.

    Allows up to `max_requests` calls within any rolling `window_seconds`
    period.  Thread-safe.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    #  Core API                                                            #
    # ------------------------------------------------------------------ #

    def is_allowed(self) -> bool:
        """
        Check whether a new request is within the rate limit.

        Returns True and records the timestamp if allowed.
        Returns False (and does NOT record) if the limit is exceeded.
        """
        now = time.monotonic()

        with self._lock:
            self._evict_expired(now)

            if len(self._timestamps) < self.max_requests:
                self._timestamps.append(now)
                return True

            return False

    def remaining(self) -> int:
        """How many more requests are allowed right now."""
        now = time.monotonic()
        with self._lock:
            self._evict_expired(now)
            return max(0, self.max_requests - len(self._timestamps))

    def reset_in(self) -> float:
        """
        Seconds until at least one request slot opens up.
        Returns 0.0 if a slot is already available.
        """
        now = time.monotonic()
        with self._lock:
            self._evict_expired(now)
            if len(self._timestamps) < self.max_requests:
                return 0.0
            # The oldest timestamp is the next one to expire
            oldest = self._timestamps[0]
            return max(0.0, (oldest + self.window_seconds) - now)

    def stats(self) -> dict:
        """Snapshot of current limiter state (useful for logging/metrics)."""
        now = time.monotonic()
        with self._lock:
            self._evict_expired(now)
            return {
                "used": len(self._timestamps),
                "remaining": max(0, self.max_requests - len(self._timestamps)),
                "limit": self.max_requests,
                "window_seconds": self.window_seconds,
                "reset_in": self.reset_in(),
            }

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _evict_expired(self, now: float) -> None:
        """Remove timestamps that have fallen outside the current window."""
        cutoff = now - self.window_seconds
        while self._timestamps and self._timestamps[0] <= cutoff:
            self._timestamps.popleft()

# 5 requests per 10-second window
limiter = RateLimiter(max_requests=5, window_seconds=10)

for i in range(7):
    allowed = limiter.is_allowed()
    print(f"Request {i+1}: {'✓ allowed' if allowed else '✗ blocked'} | {limiter.stats()}")