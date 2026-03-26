import time
from collections import deque
from threading import Lock
from abc import ABC, abstractmethod


class RateLimiter(ABC):
    """Abstract base class for rate limiters."""

    @abstractmethod
    def is_allowed(self, identifier: str = "default") -> bool:
        """Check if a request is allowed."""
        pass

    @abstractmethod
    def get_remaining(self, identifier: str = "default") -> int:
        """Get the number of remaining requests in the current window."""
        pass


class SlidingWindowRateLimiter(RateLimiter):
    """
    Rate limiter using sliding window algorithm.
    
    Maintains a timestamp history for each identifier and allows N requests
    within a rolling time window. More accurate than fixed windows.
    
    Thread-safe for concurrent access.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._request_times: dict[str, deque] = {}
        self._lock = Lock()

    def is_allowed(self, identifier: str = "default") -> bool:
        """Check if request is allowed and record timestamp if permitted."""
        with self._lock:
            current_time = time.time()

            if identifier not in self._request_times:
                self._request_times[identifier] = deque()

            requests = self._request_times[identifier]

            # Remove requests outside the sliding window
            cutoff_time = current_time - self.window_seconds
            while requests and requests[0] < cutoff_time:
                requests.popleft()

            # Check if request is allowed
            if len(requests) < self.max_requests:
                requests.append(current_time)
                return True
            return False

    def get_remaining(self, identifier: str = "default") -> int:
        """Get remaining requests in current window."""
        with self._lock:
            current_time = time.time()

            if identifier not in self._request_times:
                return self.max_requests

            requests = self._request_times[identifier]
            cutoff_time = current_time - self.window_seconds
            
            while requests and requests[0] < cutoff_time:
                requests.popleft()

            return max(0, self.max_requests - len(requests))


class FixedWindowRateLimiter(RateLimiter):
    """
    Rate limiter using fixed window algorithm.
    
    Divides time into fixed buckets. Simple and memory-efficient,
    but allows bursts at window boundaries.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._request_counts: dict[str, tuple[int, float]] = {}
        self._lock = Lock()

    def is_allowed(self, identifier: str = "default") -> bool:
        with self._lock:
            current_time = time.time()

            if identifier not in self._request_counts:
                self._request_counts[identifier] = (0, current_time)

            count, window_start = self._request_counts[identifier]

            # Check if we're in a new window
            if current_time - window_start >= self.window_seconds:
                self._request_counts[identifier] = (1, current_time)
                return True

            # Same window
            if count < self.max_requests:
                self._request_counts[identifier] = (count + 1, window_start)
                return True

            return False

    def get_remaining(self, identifier: str = "default") -> int:
        with self._lock:
            current_time = time.time()

            if identifier not in self._request_counts:
                return self.max_requests

            count, window_start = self._request_counts[identifier]

            if current_time - window_start >= self.window_seconds:
                return self.max_requests

            return max(0, self.max_requests - count)


class TokenBucketRateLimiter(RateLimiter):
    """
    Rate limiter using token bucket algorithm.
    
    Allows bursts up to max_requests, then refills at a steady rate.
    Smooth rate limiting with good fairness properties.
    """

    def __init__(self, max_requests: int, refill_rate: float):
        self.max_requests = max_requests
        self.refill_rate = refill_rate  # tokens per second
        self._buckets: dict[str, tuple[float, float]] = {}
        self._lock = Lock()

    def is_allowed(self, identifier: str = "default") -> bool:
        with self._lock:
            current_time = time.time()

            if identifier not in self._buckets:
                self._buckets[identifier] = (float(self.max_requests), current_time)

            tokens, last_refill = self._buckets[identifier]

            # Refill tokens based on time elapsed
            time_passed = current_time - last_refill
            tokens = min(self.max_requests, tokens + time_passed * self.refill_rate)

            # Try to consume a token
            if tokens >= 1.0:
                tokens -= 1.0
                self._buckets[identifier] = (tokens, current_time)
                return True

            self._buckets[identifier] = (tokens, current_time)
            return False

    def get_remaining(self, identifier: str = "default") -> int:
        with self._lock:
            current_time = time.time()

            if identifier not in self._buckets:
                return self.max_requests

            tokens, last_refill = self._buckets[identifier]
            time_passed = current_time - last_refill
            tokens = min(self.max_requests, tokens + time_passed * self.refill_rate)

            return int(tokens)

# Sliding window: 5 requests per 10 seconds
limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=10)

# Check if request is allowed for a user
if limiter.is_allowed("user123"):
    process_request()
else:
    return 429  # Too many requests

# Check remaining quota
remaining = limiter.get_remaining("user123")
print(f"Requests remaining: {remaining}")

# Token bucket: 10 req/sec burst, refill at 1 req/sec
token_limiter = TokenBucketRateLimiter(max_requests=10, refill_rate=1.0)