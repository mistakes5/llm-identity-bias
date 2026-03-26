import time
from collections import deque
from threading import Lock


class RateLimiter:
    """
    Sliding window rate limiter that allows N requests per time window.
    Thread-safe via a lock on shared state.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = Lock()

    def is_allowed(self) -> bool:
        """
        Check if a new request is allowed. If allowed, records the timestamp.
        Returns True if the request is within the rate limit, False otherwise.
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            # Evict timestamps outside the current window
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()

            if len(self._timestamps) < self.max_requests:
                self._timestamps.append(now)
                return True

            return False

    def remaining(self) -> int:
        """Returns how many requests are still allowed in the current window."""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            return max(0, self.max_requests - len(self._timestamps))

    def retry_after(self) -> float:
        """
        Returns seconds until the next request will be allowed.
        Returns 0.0 if a request is allowed right now.
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

    def reset(self) -> None:
        """Clears all recorded timestamps, fully resetting the limiter."""
        with self._lock:
            self._timestamps.clear()

    def __repr__(self) -> str:
        return (
            f"RateLimiter(max_requests={self.max_requests}, "
            f"window_seconds={self.window_seconds})"
        )


# --- Example usage ---
if __name__ == "__main__":
    limiter = RateLimiter(max_requests=5, window_seconds=10)

    print("Sending 7 requests (limit is 5 per 10s):\n")
    for i in range(1, 8):
        allowed = limiter.is_allowed()
        status = "✓ allowed" if allowed else "✗ blocked"
        print(f"  Request {i}: {status}  |  remaining={limiter.remaining()}  |  retry_after={limiter.retry_after():.2f}s")

    print(f"\nWaiting 10 seconds for window to reset...")
    time.sleep(10)
    print(f"After reset — remaining: {limiter.remaining()}")
    print(f"Request allowed: {limiter.is_allowed()}")