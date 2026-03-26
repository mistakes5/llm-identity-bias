import time
from collections import defaultdict, deque
from threading import Lock
from typing import Optional


class SlidingWindowRateLimiter:
    """
    Sliding Window rate limiter - tracks request timestamps and enforces
    N requests per time_window_seconds.

    Precise but requires O(N) space per identifier in worst case.
    Good for: API rate limits, webhook handlers, user quotas.
    """

    def __init__(self, max_requests: int, time_window_seconds: float):
        """
        Args:
            max_requests: Number of requests allowed
            time_window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window_seconds = time_window_seconds
        self.requests = defaultdict(deque)  # {identifier: deque of timestamps}
        self.lock = Lock()

    def is_allowed(self, identifier: str) -> bool:
        """Check if a request is allowed for the given identifier."""
        now = time.time()

        with self.lock:
            window_start = now - self.time_window_seconds
            request_times = self.requests[identifier]

            # Remove timestamps outside the window (O(N) but amortized O(1))
            while request_times and request_times[0] < window_start:
                request_times.popleft()

            # Check if we can allow this request
            if len(request_times) < self.max_requests:
                request_times.append(now)
                return True

            return False

    def get_remaining(self, identifier: str) -> int:
        """Get remaining requests in current window."""
        now = time.time()
        window_start = now - self.time_window_seconds

        with self.lock:
            request_times = self.requests[identifier]
            in_window = sum(1 for ts in request_times if ts >= window_start)
            return max(0, self.max_requests - in_window)

    def get_reset_time(self, identifier: str) -> Optional[float]:
        """Get seconds until the oldest request exits the window."""
        with self.lock:
            request_times = self.requests[identifier]
            if not request_times:
                return None
            oldest = request_times[0]
            reset_at = oldest + self.time_window_seconds
            return max(0, reset_at - time.time())

    def reset(self, identifier: str):
        """Clear request history for identifier."""
        with self.lock:
            self.requests.pop(identifier, None)


class TokenBucketRateLimiter:
    """
    Token Bucket - allows smooth refill over time.
    Handles bursty traffic better than fixed window.
    """

    def __init__(self, max_requests: int, refill_rate_per_second: float):
        self.max_tokens = max_requests
        self.refill_rate = refill_rate_per_second
        self.tokens = defaultdict(lambda: {"tokens": max_requests, "last_refill": time.time()})
        self.lock = Lock()

    def is_allowed(self, identifier: str, cost: int = 1) -> bool:
        now = time.time()

        with self.lock:
            bucket = self.tokens[identifier]

            # Refill tokens based on elapsed time
            elapsed = now - bucket["last_refill"]
            refilled = elapsed * self.refill_rate
            bucket["tokens"] = min(self.max_tokens, bucket["tokens"] + refilled)
            bucket["last_refill"] = now

            # Try to consume tokens
            if bucket["tokens"] >= cost:
                bucket["tokens"] -= cost
                return True
            return False

# Pseudo-code: Redis-backed sliding window
def is_allowed_redis(identifier: str) -> bool:
    key = f"ratelimit:{identifier}"
    redis.zremrangebyscore(key, 0, time.time() - self.time_window_seconds)
    count = redis.zcard(key)
    if count < self.max_requests:
        redis.zadd(key, {str(time.time()): time.time()})
        redis.expire(key, self.time_window_seconds)
        return True
    return False