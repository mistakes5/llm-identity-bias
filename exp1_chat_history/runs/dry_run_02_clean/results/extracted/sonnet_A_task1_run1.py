from collections import deque
from time import time


class RateLimiter:
    """
    Sliding window rate limiter.
    Allows up to `max_requests` calls within any `window_seconds` period.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: deque[float] = deque()

    def _evict_expired(self, now: float) -> None:
        """Remove timestamps that have fallen outside the current window."""
        cutoff = now - self.window_seconds
        while self._timestamps and self._timestamps[0] <= cutoff:
            self._timestamps.popleft()

    def is_allowed(self) -> bool:
        """
        Check whether a new request is permitted right now.
        Does NOT consume a slot — call `record()` to do that.
        """
        now = time()
        self._evict_expired(now)
        return len(self._timestamps) < self.max_requests

    def record(self) -> bool:
        """
        Attempt to consume one request slot.
        Returns True if the request was accepted, False if rate-limited.
        """
        now = time()
        self._evict_expired(now)

        if len(self._timestamps) < self.max_requests:
            self._timestamps.append(now)
            return True

        return False

    @property
    def remaining(self) -> int:
        """Slots still available in the current window."""
        self._evict_expired(time())
        return max(0, self.max_requests - len(self._timestamps))

    @property
    def timestamps(self) -> list[float]:
        """Snapshot of active request timestamps (oldest first)."""
        self._evict_expired(time())
        return list(self._timestamps)

    def retry_after(self) -> float | None:
        """
        Seconds until at least one slot frees up.
        Returns None if a slot is already available.
        """
        self._evict_expired(time())
        if len(self._timestamps) < self.max_requests:
            return None
        oldest = self._timestamps[0]
        return max(0.0, (oldest + self.window_seconds) - time())

    def __repr__(self) -> str:
        return (
            f"RateLimiter(max_requests={self.max_requests}, "
            f"window_seconds={self.window_seconds}, "
            f"active={len(self._timestamps)})"
        )


# --- example usage ---

if __name__ == "__main__":
    import time as time_module

    limiter = RateLimiter(max_requests=3, window_seconds=5)

    for i in range(5):
        accepted = limiter.record()
        status = "✓ accepted" if accepted else "✗ rate-limited"
        print(f"Request {i + 1}: {status} | remaining={limiter.remaining}")

    print(f"\nRetry after: {limiter.retry_after():.2f}s")
    print(f"Active timestamps: {limiter.timestamps}")

    print("\nWaiting 5 seconds for window to reset...")
    time_module.sleep(5)

    print(f"After reset — remaining={limiter.remaining}")
    print(f"Request 6: {'✓ accepted' if limiter.record() else '✗ rate-limited'}")