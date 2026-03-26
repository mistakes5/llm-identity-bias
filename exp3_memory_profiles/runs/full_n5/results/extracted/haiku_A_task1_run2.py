# SLIDING WINDOW (Most Accurate) ⭐ Recommended
# - Tracks actual timestamps of each request
# - O(N) memory, but highly accurate—no edge-case bursts
# - Best for APIs where precision matters (billing, quotas)

# TOKEN BUCKET (Best for Bursts)
# - Allows traffic bursts up to the cap, then refills at steady rate
# - O(1) memory—only tracks tokens and refill time
# - Good for bursty workloads (downloads, batch processing)

# FIXED WINDOW (Simplest, but Inaccurate)
# - Resets at fixed intervals (e.g., every 60 seconds)
# - O(1) memory
# - ⚠️  Can allow double-rate bursts at window boundaries

import time
import threading
from collections import deque
from typing import Optional
from abc import ABC, abstractmethod


class RateLimiter(ABC):
    @abstractmethod
    def is_allowed(self) -> bool:
        pass

    @abstractmethod
    def get_remaining(self) -> int:
        pass


class SlidingWindowRateLimiter(RateLimiter):
    """Most accurate: tracks actual request timestamps in a rolling window."""

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.timestamps: deque = deque()
        self._lock = threading.Lock()

    def is_allowed(self) -> bool:
        with self._lock:
            now = time.time()
            window_start = now - self.window_seconds

            # Remove expired timestamps
            while self.timestamps and self.timestamps[0] < window_start:
                self.timestamps.popleft()

            if len(self.timestamps) < self.max_requests:
                self.timestamps.append(now)
                return True
            return False

    def get_remaining(self) -> int:
        with self._lock:
            now = time.time()
            window_start = now - self.window_seconds
            while self.timestamps and self.timestamps[0] < window_start:
                self.timestamps.popleft()
            return max(0, self.max_requests - len(self.timestamps))

    def get_reset_time(self) -> Optional[float]:
        """Returns Unix timestamp when oldest request expires."""
        with self._lock:
            if not self.timestamps:
                return None
            return self.timestamps[0] + self.window_seconds


class TokenBucketRateLimiter(RateLimiter):
    """Allows bursts, then refills at steady rate. Best for variable traffic."""

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.tokens = float(max_requests)
        self.last_refill = time.time()
        self._lock = threading.Lock()

    def is_allowed(self) -> bool:
        with self._lock:
            self._refill()
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False

    def _refill(self) -> None:
        now = time.time()
        elapsed = now - self.last_refill
        # Refill rate = max_requests / window_seconds
        tokens_to_add = (elapsed / self.window_seconds) * self.max_requests
        self.tokens = min(self.max_requests, self.tokens + tokens_to_add)
        self.last_refill = now

    def get_remaining(self) -> int:
        with self._lock:
            self._refill()
            return int(self.tokens)


class FixedWindowRateLimiter(RateLimiter):
    """Simplest, but allows bursts at window boundaries."""

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.request_count = 0
        self.window_start = time.time()
        self._lock = threading.Lock()

    def is_allowed(self) -> bool:
        with self._lock:
            now = time.time()
            if now - self.window_start >= self.window_seconds:
                self.request_count = 0
                self.window_start = now

            if self.request_count < self.max_requests:
                self.request_count += 1
                return True
            return False

    def get_remaining(self) -> int:
        with self._lock:
            now = time.time()
            if now - self.window_start >= self.window_seconds:
                return self.max_requests
            return max(0, self.max_requests - self.request_count)

# Example 1: 10 requests per 60 seconds (sliding window)
limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=60)

if limiter.is_allowed():
    print("Request allowed")
    print(f"Remaining: {limiter.get_remaining()}")
else:
    print("Rate limit exceeded")


# Example 2: API decorator
def rate_limited(limiter):
    def decorator(func):
        def wrapper(*args, **kwargs):
            if not limiter.is_allowed():
                raise Exception("Rate limit exceeded")
            return func(*args, **kwargs)
        return wrapper
    return decorator

limiter = TokenBucketRateLimiter(max_requests=100, window_seconds=60)

@rate_limited(limiter)
def fetch_data():
    return "data"


# Example 3: Test with concurrent requests
import concurrent.futures

limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=2)

def make_request(i):
    allowed = limiter.is_allowed()
    status = "✓" if allowed else "✗"
    return f"Request {i}: {status} (remaining: {limiter.get_remaining()})"

with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    results = list(executor.map(make_request, range(12)))
    for r in results:
        print(r)