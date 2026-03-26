import time
import threading
from collections import deque
from dataclasses import dataclass, field


@dataclass
class RateLimiter:
    """
    Sliding window rate limiter.

    Allows up to `max_requests` requests within any rolling `window_seconds` window.
    Thread-safe via an internal lock.
    """
    max_requests: int
    window_seconds: float
    _timestamps: deque = field(default_factory=deque, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def _evict_expired(self, now: float) -> None:
        """Remove timestamps that have fallen outside the current window."""
        cutoff = now - self.window_seconds
        while self._timestamps and self._timestamps[0] <= cutoff:
            self._timestamps.popleft()

    def is_allowed(self) -> bool:
        """
        Check whether the next request is within the rate limit.

        Returns True and records the timestamp if allowed; False otherwise.
        """
        now = time.monotonic()
        with self._lock:
            self._evict_expired(now)
            if len(self._timestamps) < self.max_requests:
                self._timestamps.append(now)
                return True
            return False

    def retry_after(self) -> float:
        """
        Seconds until the next request slot opens up.

        Returns 0.0 if a request is currently allowed.
        """
        now = time.monotonic()
        with self._lock:
            self._evict_expired(now)
            if len(self._timestamps) < self.max_requests:
                return 0.0
            # Oldest timestamp + window = when the first slot frees up
            return self._timestamps[0] + self.window_seconds - now

    @property
    def current_count(self) -> int:
        """Number of requests recorded in the current window."""
        now = time.monotonic()
        with self._lock:
            self._evict_expired(now)
            return len(self._timestamps)

    @property
    def remaining(self) -> int:
        """Remaining request slots in the current window."""
        return max(0, self.max_requests - self.current_count)

    def __repr__(self) -> str:
        return (
            f"RateLimiter(max_requests={self.max_requests}, "
            f"window_seconds={self.window_seconds}, "
            f"current_count={self.current_count})"
        )


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    limiter = RateLimiter(max_requests=5, window_seconds=10)

    print("Sending 7 requests immediately:")
    for i in range(1, 8):
        allowed = limiter.is_allowed()
        status = "✓ allowed" if allowed else f"✗ blocked (retry in {limiter.retry_after():.2f}s)"
        print(f"  Request {i}: {status}  — remaining slots: {limiter.remaining}")

    print(f"\nFinal state: {limiter}")