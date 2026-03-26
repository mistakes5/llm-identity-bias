# rate_limiter.py

import time
from collections import deque
from threading import Lock
from typing import Dict, Optional


class RateLimiter:
    """
    Sliding window rate limiter.
    Allows up to `max_requests` per `window_seconds` for any tracked key.
    Thread-safe via per-key locking.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: Dict[str, deque] = {}
        self._lock = Lock()

    def is_allowed(self, key: str = "default") -> bool:
        """
        Check if a request from `key` is allowed right now.
        Automatically records the timestamp if allowed.

        Returns True if allowed, False if rate limit exceeded.
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            if key not in self._buckets:
                self._buckets[key] = deque()

            bucket = self._buckets[key]

            # Evict timestamps outside the sliding window
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) < self.max_requests:
                bucket.append(now)
                return True

            return False

    def remaining(self, key: str = "default") -> int:
        """How many requests are still allowed in the current window."""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            bucket = self._buckets.get(key, deque())
            active = sum(1 for t in bucket if t > cutoff)
            return max(0, self.max_requests - active)

    def reset_at(self, key: str = "default") -> Optional[float]:
        """
        Seconds until the oldest request expires (freeing a slot).
        Returns None if the bucket is empty or under the limit.
        """
        with self._lock:
            bucket = self._buckets.get(key)
            if not bucket or len(bucket) < self.max_requests:
                return None
            oldest = bucket[0]
            return max(0.0, oldest + self.window_seconds - time.monotonic())

    def get_timestamps(self, key: str = "default") -> list[float]:
        """Return a snapshot of active request timestamps for `key`."""
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            bucket = self._buckets.get(key, deque())
            return [t for t in bucket if t > cutoff]

    def clear(self, key: str = "default") -> None:
        """Reset the bucket for a specific key."""
        with self._lock:
            self._buckets.pop(key, None)

# demo.py

from rate_limiter import RateLimiter


def main():
    # 5 requests per 10-second window
    limiter = RateLimiter(max_requests=5, window_seconds=10)

    print("=== Basic Allow/Deny ===")
    for i in range(7):
        allowed = limiter.is_allowed("user:42")
        remaining = limiter.remaining("user:42")
        status = "✅ allowed" if allowed else "❌ denied"
        print(f"  Request {i+1}: {status} | remaining slots: {remaining}")

    print("\n=== Reset At ===")
    wait = limiter.reset_at("user:42")
    print(f"  Next slot opens in ~{wait:.2f}s")

    print("\n=== Timestamps ===")
    ts = limiter.get_timestamps("user:42")
    print(f"  {len(ts)} active timestamps recorded")

    print("\n=== Multiple Keys ===")
    for user in ["alice", "bob", "alice", "alice"]:
        allowed = limiter.is_allowed(user)
        print(f"  {user}: {'✅' if allowed else '❌'} | remaining: {limiter.remaining(user)}")


if __name__ == "__main__":
    main()