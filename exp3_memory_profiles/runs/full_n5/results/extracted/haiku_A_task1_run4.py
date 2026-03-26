import time
from collections import deque
from typing import Optional
from threading import Lock
from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    remaining: int
    reset_at: Optional[float] = None


class RateLimiter(ABC):
    """Abstract base class for rate limiters."""

    @abstractmethod
    def is_allowed(self, identifier: str = "default") -> bool:
        pass

    @abstractmethod
    def check(self, identifier: str = "default") -> RateLimitResult:
        pass


class SlidingWindowRateLimiter(RateLimiter):
    """
    SLIDING WINDOW - Most accurate and fair.
    
    Tracks exact timestamps of requests within a rolling time window.
    Rejects request if count in window >= limit.
    
    ✓ Fair - no burst allowance
    ✓ Accurate - true N requests per window
    ✗ Memory - stores all timestamps
    
    Best for: API rate limiting, strict fairness required
    """

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}  # identifier -> deque of timestamps
        self._lock = Lock()

    def is_allowed(self, identifier: str = "default") -> bool:
        return self.check(identifier).allowed

    def check(self, identifier: str = "default") -> RateLimitResult:
        now = time.time()

        with self._lock:
            if identifier not in self.requests:
                self.requests[identifier] = deque()

            request_queue = self.requests[identifier]
            window_start = now - self.window_seconds

            # Remove timestamps outside the window
            while request_queue and request_queue[0] < window_start:
                request_queue.popleft()

            request_count = len(request_queue)
            allowed = request_count < self.max_requests

            if allowed:
                request_queue.append(now)
                remaining = self.max_requests - (request_count + 1)
            else:
                remaining = 0

            # When will oldest request expire from window?
            reset_at = request_queue[0] + self.window_seconds if request_queue else None

        return RateLimitResult(allowed=allowed, remaining=remaining, reset_at=reset_at)


class TokenBucketRateLimiter(RateLimiter):
    """
    TOKEN BUCKET - Allows controlled bursts.
    
    Tokens refill at constant rate. Requests consume tokens.
    Allows burst up to capacity at any moment.
    
    ✓ Handles traffic spikes gracefully
    ✓ Smooth, predictable rate
    ✗ Can exceed average rate briefly
    
    Best for: APIs expecting bursty traffic
    """

    def __init__(self, capacity: int, refill_rate: float, window_seconds: int = 1):
        """
        Args:
            capacity: Max tokens (bucket size)
            refill_rate: Tokens added per window_seconds
            window_seconds: Refill period (default 1 second)
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.window_seconds = window_seconds
        self.buckets = {}
        self._lock = Lock()

    def is_allowed(self, identifier: str = "default") -> bool:
        return self.check(identifier).allowed

    def check(self, identifier: str = "default") -> RateLimitResult:
        now = time.time()

        with self._lock:
            if identifier not in self.buckets:
                self.buckets[identifier] = {
                    "tokens": self.capacity,
                    "last_refill": now
                }

            bucket = self.buckets[identifier]

            # Calculate refill based on elapsed time
            elapsed = now - bucket["last_refill"]
            refill_amount = (elapsed / self.window_seconds) * self.refill_rate
            bucket["tokens"] = min(self.capacity, bucket["tokens"] + refill_amount)
            bucket["last_refill"] = now

            allowed = bucket["tokens"] >= 1

            if allowed:
                bucket["tokens"] -= 1
                remaining = int(bucket["tokens"])
            else:
                remaining = 0

            # When will next token be available?
            reset_at = None
            if bucket["tokens"] < 1:
                tokens_needed = 1 - bucket["tokens"]
                reset_at = now + (tokens_needed / self.refill_rate) * self.window_seconds

        return RateLimitResult(allowed=allowed, remaining=remaining, reset_at=reset_at)


class FixedWindowRateLimiter(RateLimiter):
    """
    FIXED WINDOW - Simple but allows boundary burst.
    
    Divides time into fixed intervals. Counts requests per interval.
    
    ✓ Simple implementation
    ✓ Low memory
    ✗ Can allow 2x burst at window boundaries
    
    Best for: Simple quota systems, less critical limits
    """

    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.windows = {}
        self._lock = Lock()

    def is_allowed(self, identifier: str = "default") -> bool:
        return self.check(identifier).allowed

    def check(self, identifier: str = "default") -> RateLimitResult:
        now = time.time()
        current_window = int(now / self.window_seconds)

        with self._lock:
            if identifier not in self.windows:
                self.windows[identifier] = {"count": 0, "window": current_window}

            window_data = self.windows[identifier]

            # Reset if we've entered a new window
            if window_data["window"] != current_window:
                window_data["count"] = 0
                window_data["window"] = current_window

            allowed = window_data["count"] < self.max_requests

            if allowed:
                window_data["count"] += 1
                remaining = self.max_requests - window_data["count"]
            else:
                remaining = 0

            reset_at = (current_window + 1) * self.window_seconds

        return RateLimitResult(allowed=allowed, remaining=remaining, reset_at=reset_at)


# Usage examples
if __name__ == "__main__":
    # Example 1: Simple check
    limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=60)
    
    if limiter.is_allowed("user_123"):
        print("Request allowed - process it")
    else:
        print("Rate limited - reject request")
    
    # Example 2: Get detailed result
    result = limiter.check("user_123")
    if result.allowed:
        print(f"Remaining: {result.remaining} requests")
    else:
        wait_seconds = result.reset_at - time.time()
        print(f"Retry after {wait_seconds:.1f} seconds")
    
    # Example 3: API endpoint pattern
    active_limiter = SlidingWindowRateLimiter(max_requests=100, window_seconds=3600)
    
    user_id = "user_456"
    result = active_limiter.check(user_id)
    
    headers = {
        "X-RateLimit-Remaining": str(result.remaining),
        "X-RateLimit-Reset": str(int(result.reset_at)) if result.reset_at else "0"
    }
    
    if not result.allowed:
        print(f"429 Too Many Requests. Reset at: {result.reset_at}")
    else:
        print(f"Request allowed. {result.remaining} remaining.")

limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=60)

if limiter.is_allowed(user_id):
    process_request()
else:
    return 429  # Too Many Requests

result = limiter.check(user_id)
headers = {
    "X-RateLimit-Remaining": str(result.remaining),
    "X-RateLimit-Reset": str(int(result.reset_at))
}

if not result.allowed:
    return 429, headers, "Rate limit exceeded"
else:
    return 200, headers, response_data

# Free tier: 100 req/hour
free_limiter = SlidingWindowRateLimiter(100, 3600)

# Pro tier: 10,000 req/hour
pro_limiter = SlidingWindowRateLimiter(10000, 3600)

limiter = pro_limiter if user.is_pro else free_limiter