import time
from collections import deque
from threading import Lock
from abc import ABC, abstractmethod
from typing import Dict, Any


class RateLimiter(ABC):
    """Abstract base class for rate limiting strategies."""

    @abstractmethod
    def is_allowed(self, key: str = "default") -> bool:
        """Check if a request is allowed for the given key."""
        pass

    @abstractmethod
    def get_status(self, key: str = "default") -> Dict[str, Any]:
        """Get current rate limit status."""
        pass

    @abstractmethod
    def reset(self, key: str = "default") -> None:
        """Reset rate limit for the given key."""
        pass


class SlidingWindowRateLimiter(RateLimiter):
    """
    Sliding window rate limiter - most accurate approach.
    Tracks actual request timestamps and removes ones outside the window.
    """

    def __init__(self, max_requests: int, time_window: float):
        self.max_requests = max_requests
        self.time_window = time_window
        self._requests: Dict[str, deque] = {}
        self._lock = Lock()

    def is_allowed(self, key: str = "default") -> bool:
        with self._lock:
            current_time = time.time()
            
            if key not in self._requests:
                self._requests[key] = deque()

            # Remove old timestamps outside window
            cutoff_time = current_time - self.time_window
            while self._requests[key] and self._requests[key][0] < cutoff_time:
                self._requests[key].popleft()

            # Check quota
            if len(self._requests[key]) < self.max_requests:
                self._requests[key].append(current_time)
                return True
            return False

    def get_status(self, key: str = "default") -> Dict[str, Any]:
        with self._lock:
            current_time = time.time()
            
            if key not in self._requests:
                return {
                    "current_requests": 0,
                    "remaining": self.max_requests,
                    "reset_time": current_time + self.time_window,
                    "status": "available"
                }

            # Clean up old timestamps
            cutoff_time = current_time - self.time_window
            while self._requests[key] and self._requests[key][0] < cutoff_time:
                self._requests[key].popleft()

            current_requests = len(self._requests[key])
            reset_time = (
                self._requests[key][0] + self.time_window
                if self._requests[key]
                else current_time + self.time_window
            )

            return {
                "current_requests": current_requests,
                "remaining": max(0, self.max_requests - current_requests),
                "reset_time": reset_time,
                "reset_in_seconds": max(0, reset_time - current_time),
                "status": "available" if current_requests < self.max_requests else "rate_limited"
            }

    def reset(self, key: str = "default") -> None:
        with self._lock:
            if key in self._requests:
                self._requests[key].clear()


class FixedWindowRateLimiter(RateLimiter):
    """
    Fixed window rate limiter - simpler, lower overhead.
    Resets counter at each time window boundary.
    """

    def __init__(self, max_requests: int, time_window: float):
        self.max_requests = max_requests
        self.time_window = time_window
        self._windows: Dict[str, tuple] = {}
        self._lock = Lock()

    def is_allowed(self, key: str = "default") -> bool:
        with self._lock:
            current_time = time.time()
            current_window = int(current_time / self.time_window)

            if key not in self._windows:
                self._windows[key] = (current_window, 0)

            window_start, count = self._windows[key]

            # Check if we've moved to a new window
            if window_start != current_window:
                self._windows[key] = (current_window, 0)
                count = 0

            # Check quota
            if count < self.max_requests:
                self._windows[key] = (current_window, count + 1)
                return True
            return False

    def get_status(self, key: str = "default") -> Dict[str, Any]:
        with self._lock:
            current_time = time.time()
            current_window = int(current_time / self.time_window)

            if key not in self._windows:
                reset_time = (current_window + 1) * self.time_window
                return {
                    "current_requests": 0,
                    "remaining": self.max_requests,
                    "reset_time": reset_time,
                    "reset_in_seconds": reset_time - current_time,
                    "status": "available"
                }

            window_start, count = self._windows[key]
            if window_start != current_window:
                count = 0

            reset_time = (current_window + 1) * self.time_window

            return {
                "current_requests": count,
                "remaining": max(0, self.max_requests - count),
                "reset_time": reset_time,
                "reset_in_seconds": reset_time - current_time,
                "status": "available" if count < self.max_requests else "rate_limited"
            }

    def reset(self, key: str = "default") -> None:
        with self._lock:
            if key in self._windows:
                self._windows[key] = (self._windows[key][0], 0)


class TokenBucketRateLimiter(RateLimiter):
    """
    Token bucket algorithm - allows controlled bursts.
    Tokens refill at constant rate; each request consumes one.
    """

    def __init__(self, max_requests: int, time_window: float):
        self.max_requests = max_requests
        self.time_window = time_window
        self.refill_rate = max_requests / time_window
        self._buckets: Dict[str, tuple] = {}
        self._lock = Lock()

    def _refill(self, key: str, current_time: float) -> None:
        if key not in self._buckets:
            self._buckets[key] = (self.max_requests, current_time)
            return

        tokens, last_refill = self._buckets[key]
        elapsed = current_time - last_refill
        new_tokens = min(
            self.max_requests,
            tokens + elapsed * self.refill_rate
        )
        self._buckets[key] = (new_tokens, current_time)

    def is_allowed(self, key: str = "default") -> bool:
        with self._lock:
            current_time = time.time()
            self._refill(key, current_time)
            tokens, _ = self._buckets[key]

            if tokens >= 1.0:
                self._buckets[key] = (tokens - 1.0, current_time)
                return True
            return False

    def get_status(self, key: str = "default") -> Dict[str, Any]:
        with self._lock:
            current_time = time.time()
            self._refill(key, current_time)
            tokens, _ = self._buckets.get(key, (self.max_requests, current_time))

            return {
                "available_tokens": round(tokens, 2),
                "bucket_capacity": self.max_requests,
                "refill_rate": round(self.refill_rate, 4),
                "status": "available" if tokens >= 1.0 else "rate_limited"
            }

    def reset(self, key: str = "default") -> None:
        with self._lock:
            current_time = time.time()
            self._buckets[key] = (self.max_requests, current_time)

# 5 requests per 60 seconds using sliding window (default, most accurate)
limiter = SlidingWindowRateLimiter(max_requests=5, time_window=60)

# Check if request is allowed
if limiter.is_allowed("user_123"):
    print("Request allowed")
else:
    print("Rate limited - try again later")

# Get status
status = limiter.get_status("user_123")
print(f"Remaining: {status['remaining']}")
print(f"Reset in: {status['reset_in_seconds']} seconds")

# Reset a user's limit
limiter.reset("user_123")

# Alternative: Use fixed window (simpler, slightly lower memory)
limiter = FixedWindowRateLimiter(max_requests=10, time_window=60)

# Alternative: Use token bucket (allows bursts)
limiter = TokenBucketRateLimiter(max_requests=10, time_window=60)