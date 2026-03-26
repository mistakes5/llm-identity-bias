"""
Rate limiter implementations for controlling request throughput.

Supports multiple strategies:
- SlidingWindowRateLimiter: Accurate, removes old requests outside the window
- FixedWindowRateLimiter: Simple, efficient, but has edge cases at boundaries
- TokenBucketRateLimiter: Smooth throughput, allows controlled bursts
"""

import time
import threading
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from typing import Optional, Dict


class RateLimiter(ABC):
    """Base class for rate limiters."""

    @abstractmethod
    def is_allowed(self, key: str) -> bool:
        """Check if a request is allowed for the given key."""
        pass

    @abstractmethod
    def get_remaining(self, key: str) -> int:
        """Get remaining requests for the given key."""
        pass


class SlidingWindowRateLimiter(RateLimiter):
    """
    Sliding window rate limiter using timestamp tracking.

    Most accurate approach: removes requests older than the time window,
    providing true per-window rate limiting without boundary issues.

    Trade-off: Uses more memory (stores all request timestamps).
    """

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        """Check if a request is allowed. Removes old timestamps automatically."""
        with self.lock:
            now = time.time()
            window_start = now - self.window_seconds

            # Remove old requests outside the window
            while self.requests[key] and self.requests[key][0] < window_start:
                self.requests[key].popleft()

            # Check if we're under the limit
            if len(self.requests[key]) < self.max_requests:
                self.requests[key].append(now)
                return True
            return False

    def get_remaining(self, key: str) -> int:
        """Get remaining requests for this key in the current window."""
        with self.lock:
            now = time.time()
            window_start = now - self.window_seconds
            valid_requests = sum(
                1 for timestamp in self.requests[key]
                if timestamp >= window_start
            )
            return max(0, self.max_requests - valid_requests)


class FixedWindowRateLimiter(RateLimiter):
    """Simple bucket-based limiter. Fast but has boundary edge cases."""

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.windows: Dict[str, int] = {}
        self.lock = threading.Lock()

    def _get_window_key(self, key: str, now: float) -> str:
        bucket = int(now / self.window_seconds)
        return f"{key}:{bucket}"

    def is_allowed(self, key: str) -> bool:
        with self.lock:
            now = time.time()
            window_key = self._get_window_key(key, now)
            count = self.windows.get(window_key, 0)

            if count < self.max_requests:
                self.windows[window_key] = count + 1
                return True
            return False

    def get_remaining(self, key: str) -> int:
        with self.lock:
            now = time.time()
            window_key = self._get_window_key(key, now)
            count = self.windows.get(window_key, 0)
            return max(0, self.max_requests - count)


class TokenBucketRateLimiter(RateLimiter):
    """Smooth throughput limiter. Allows bursts when tokens available."""

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_tokens = max_requests
        self.refill_rate = max_requests / window_seconds
        self.buckets: Dict[str, dict] = {}
        self.lock = threading.Lock()

    def _get_bucket(self, key: str) -> dict:
        if key not in self.buckets:
            self.buckets[key] = {"tokens": self.max_tokens, "last_refill": time.time()}
        return self.buckets[key]

    def _refill(self, bucket: dict, now: float) -> None:
        elapsed = now - bucket["last_refill"]
        bucket["tokens"] = min(self.max_tokens, bucket["tokens"] + elapsed * self.refill_rate)
        bucket["last_refill"] = now

    def is_allowed(self, key: str) -> bool:
        with self.lock:
            now = time.time()
            bucket = self._get_bucket(key)
            self._refill(bucket, now)
            if bucket["tokens"] >= 1:
                bucket["tokens"] -= 1
                return True
            return False

    def get_remaining(self, key: str) -> int:
        with self.lock:
            now = time.time()
            bucket = self._get_bucket(key)
            self._refill(bucket, now)
            return int(bucket["tokens"])

# Create a limiter: 5 requests per 60 seconds
limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60)

# Check if request is allowed
if limiter.is_allowed("user_123"):
    print("Request allowed")
else:
    print("Rate limit exceeded")

# Check remaining quota
remaining = limiter.get_remaining("user_123")
print(f"Remaining: {remaining} requests")