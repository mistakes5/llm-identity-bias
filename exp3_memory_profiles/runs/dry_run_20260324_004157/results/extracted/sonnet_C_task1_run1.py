# rate_limiter.py
from collections import deque
import time
import threading


class RateLimiter:
    """
    Sliding window rate limiter.

    Allows up to `max_requests` calls within any rolling `window_seconds` span.
    Thread-safe by default.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    def is_allowed(self) -> bool:
        """
        Check whether a new request is permitted right now.
        If allowed, the current timestamp is recorded automatically.
        Returns True if the request is within the rate limit, False otherwise.
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            # Drop timestamps that have slid out of the window
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()

            if len(self._timestamps) < self.max_requests:
                self._timestamps.append(now)
                return True

            return False  # Limit exceeded — request denied

    def remaining(self) -> int:
        """How many more requests are allowed right now."""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            return max(0, self.max_requests - len(self._timestamps))

    def retry_after(self) -> float:
        """
        Seconds until the next request slot opens up.
        Returns 0.0 if a request is already allowed.
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()

            if len(self._timestamps) < self.max_requests:
                return 0.0

            # Oldest timestamp + window = when the next slot opens
            return self._timestamps[0] + self.window_seconds - now

    def get_timestamps(self) -> list[float]:
        """Return a snapshot of all tracked request timestamps (monotonic clock)."""
        with self._lock:
            return list(self._timestamps)

    def reset(self) -> None:
        """Clear all recorded timestamps (useful for testing)."""
        with self._lock:
            self._timestamps.clear()


class MultiKeyRateLimiter:
    """
    Per-key rate limiter — useful for per-user or per-IP limiting.

    Example:
        limiter = MultiKeyRateLimiter(max_requests=10, window_seconds=60)
        limiter.is_allowed("user_42")   # True/False per user
    """

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._limiters: dict[str, RateLimiter] = {}
        self._lock = threading.Lock()

    def _get_limiter(self, key: str) -> RateLimiter:
        with self._lock:
            if key not in self._limiters:
                self._limiters[key] = RateLimiter(
                    self.max_requests, self.window_seconds
                )
            return self._limiters[key]

    def is_allowed(self, key: str) -> bool:
        return self._get_limiter(key).is_allowed()

    def remaining(self, key: str) -> int:
        return self._get_limiter(key).remaining()

    def retry_after(self, key: str) -> float:
        return self._get_limiter(key).retry_after()

# --- Single limiter: 5 requests per 10 seconds ---
limiter = RateLimiter(max_requests=5, window_seconds=10)

for i in range(7):
    allowed = limiter.is_allowed()
    print(f"Request {i+1}: {'✓ allowed' if allowed else '✗ denied'} | "
          f"remaining={limiter.remaining()} | "
          f"retry_after={limiter.retry_after():.2f}s")

# Request 1: ✓ allowed | remaining=4 | retry_after=0.00s
# Request 2: ✓ allowed | remaining=3 | retry_after=0.00s
# ...
# Request 6: ✗ denied  | remaining=0 | retry_after=9.98s
# Request 7: ✗ denied  | remaining=0 | retry_after=9.97s

# --- Per-user limiter ---
users = MultiKeyRateLimiter(max_requests=3, window_seconds=60)
print(users.is_allowed("alice"))  # True
print(users.is_allowed("alice"))  # True
print(users.is_allowed("bob"))    # True — independent bucket
print(users.remaining("alice"))   # 1