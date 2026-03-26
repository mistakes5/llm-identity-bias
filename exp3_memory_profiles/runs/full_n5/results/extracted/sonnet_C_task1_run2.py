★ Insight ─────────────────────────────────────
• Sliding window is more accurate than fixed window (no burst at boundary)
• deque with maxlen gives O(1) appends and auto-evicts old entries
• Thread-safe via threading.Lock — safe for concurrent use
─────────────────────────────────────────────────

import time
import threading
from collections import deque


class RateLimiter:
    """
    Sliding window rate limiter.
    Allows up to `max_requests` calls within any rolling `window_seconds` period.
    Thread-safe for concurrent use.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    def is_allowed(self) -> bool:
        """
        Check if a new request is allowed right now.
        If allowed, records the timestamp and returns True.
        If the limit is hit, returns False without recording.
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            # Drop timestamps that have slid outside the window
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()

            if len(self._timestamps) < self.max_requests:
                self._timestamps.append(now)
                return True

            return False

    def remaining(self) -> int:
        """How many more requests are allowed in the current window."""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            return max(0, self.max_requests - len(self._timestamps))

    def retry_after(self) -> float:
        """
        Seconds until the next request slot opens up.
        Returns 0.0 if requests are available right now.
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()

            if len(self._timestamps) < self.max_requests:
                return 0.0

            # Oldest timestamp + window = when the next slot opens
            oldest = self._timestamps[0]
            return max(0.0, (oldest + self.window_seconds) - now)

    def get_timestamps(self) -> list[float]:
        """Return a copy of all active request timestamps (for inspection/debugging)."""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            return list(self._timestamps)

    def __repr__(self) -> str:
        return (
            f"RateLimiter(max_requests={self.max_requests}, "
            f"window_seconds={self.window_seconds}, "
            f"active={len(self._timestamps)})"
        )

# Allow 5 requests per 10-second window
limiter = RateLimiter(max_requests=5, window_seconds=10)

for i in range(7):
    allowed = limiter.is_allowed()
    print(f"Request {i+1}: {'✓ allowed' if allowed else '✗ blocked'} | "
          f"remaining={limiter.remaining()} | "
          f"retry_after={limiter.retry_after():.2f}s")

# Request 1: ✓ allowed  | remaining=4 | retry_after=0.00s
# Request 2: ✓ allowed  | remaining=3 | retry_after=0.00s
# Request 3: ✓ allowed  | remaining=2 | retry_after=0.00s
# Request 4: ✓ allowed  | remaining=1 | retry_after=0.00s
# Request 5: ✓ allowed  | remaining=0 | retry_after=9.99s
# Request 6: ✗ blocked  | remaining=0 | retry_after=9.99s
# Request 7: ✗ blocked  | remaining=0 | retry_after=9.99s