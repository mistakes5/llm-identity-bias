# rate_limiter.py
from collections import deque
from threading import Lock
import time


class RateLimiter:
    """
    Sliding-window rate limiter.

    Allows up to `max_requests` calls within any rolling `window_seconds`
    period. Supports optional per-key limiting (e.g. per user/IP).
    Thread-safe.

    Example:
        limiter = RateLimiter(max_requests=5, window_seconds=10)

        if limiter.is_allowed("user_42"):
            process_request()
        else:
            return "429 Too Many Requests"
    """

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = {}
        self._lock = Lock()

    # ── Core API ──────────────────────────────────────────────────────────

    def is_allowed(self, key: str = "default") -> bool:
        """
        Check if a new request is allowed for `key`.
        Records the request timestamp if allowed.

        Returns True if allowed, False if rate-limited.
        """
        with self._lock:
            now = time.monotonic()
            timestamps = self._get_bucket(key)
            self._evict_expired(timestamps, now)

            if len(timestamps) < self.max_requests:
                timestamps.append(now)
                return True
            return False

    def remaining(self, key: str = "default") -> int:
        """How many requests are still allowed in the current window."""
        with self._lock:
            now = time.monotonic()
            timestamps = self._get_bucket(key)
            self._evict_expired(timestamps, now)
            return max(0, self.max_requests - len(timestamps))

    def reset_at(self, key: str = "default") -> float | None:
        """
        Returns the Unix timestamp when the oldest request expires
        (i.e. when one more slot opens up). Returns None if no requests
        have been made.
        """
        with self._lock:
            timestamps = self._get_bucket(key)
            if not timestamps:
                return None
            return time.time() + (self.window_seconds - (time.monotonic() - timestamps[0]))

    def get_timestamps(self, key: str = "default") -> list[float]:
        """Return a snapshot of all active request timestamps for `key`."""
        with self._lock:
            now = time.monotonic()
            timestamps = self._get_bucket(key)
            self._evict_expired(timestamps, now)
            # Convert monotonic → wall time for human-readable output
            wall_offset = time.time() - time.monotonic()
            return [t + wall_offset for t in timestamps]

    def reset(self, key: str = "default") -> None:
        """Clear all recorded requests for `key`."""
        with self._lock:
            self._buckets.pop(key, None)

    # ── Internals ─────────────────────────────────────────────────────────

    def _get_bucket(self, key: str) -> deque[float]:
        if key not in self._buckets:
            self._buckets[key] = deque()
        return self._buckets[key]

    def _evict_expired(self, timestamps: deque[float], now: float) -> None:
        """Drop timestamps older than the sliding window."""
        cutoff = now - self.window_seconds
        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()

# demo.py
from rate_limiter import RateLimiter


def demo():
    limiter = RateLimiter(max_requests=3, window_seconds=5)

    print("── Allow 3 requests ──")
    for i in range(3):
        allowed = limiter.is_allowed("alice")
        print(f"  Request {i+1}: {'✓ allowed' if allowed else '✗ blocked'} "
              f"| remaining: {limiter.remaining('alice')}")

    print("\n── 4th request should be blocked ──")
    allowed = limiter.is_allowed("alice")
    print(f"  Request 4: {'✓ allowed' if allowed else '✗ blocked'}")
    print(f"  Window resets at: {limiter.reset_at('alice'):.2f} (unix)")

    print("\n── Different key is independent ──")
    allowed = limiter.is_allowed("bob")
    print(f"  Bob request 1: {'✓ allowed' if allowed else '✗ blocked'}")

    print("\n── Wait 5s, window slides, Alice gets slots back ──")
    time.sleep(5.1)
    allowed = limiter.is_allowed("alice")
    print(f"  Request 5 (after wait): {'✓ allowed' if allowed else '✗ blocked'} "
          f"| remaining: {limiter.remaining('alice')}")


if __name__ == "__main__":
    demo()