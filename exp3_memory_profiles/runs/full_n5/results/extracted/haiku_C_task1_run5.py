import time
from collections import deque
from threading import Lock
from typing import Dict


class RateLimiter:
    """
    Sliding window rate limiter.
    Allows N requests per time window with O(N) cleanup.
    Thread-safe for concurrent usage.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        """
        Args:
            max_requests: Maximum number of requests allowed per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = deque()  # Stores timestamps of requests
        self.lock = Lock()

    def is_allowed(self) -> bool:
        """Check if a request is allowed. Updates internal state."""
        with self.lock:
            now = time.time()

            # Remove requests outside the window
            while self.requests and self.requests[0] < now - self.window_seconds:
                self.requests.popleft()

            # Allow if under limit
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True

            return False

    def get_remaining(self) -> int:
        """Get number of remaining requests in current window."""
        with self.lock:
            now = time.time()
            while self.requests and self.requests[0] < now - self.window_seconds:
                self.requests.popleft()
            return self.max_requests - len(self.requests)

    def get_reset_time(self) -> float:
        """Seconds until oldest request expires (next slot available)."""
        with self.lock:
            if not self.requests:
                return 0.0
            oldest = self.requests[0]
            reset = oldest + self.window_seconds - time.time()
            return max(0.0, reset)


class MultiKeyRateLimiter:
    """
    Per-identifier rate limiter (e.g., by IP, user ID, API key).
    Each identifier gets independent N requests per window.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.limiters: Dict[str, RateLimiter] = {}
        self.lock = Lock()

    def is_allowed(self, identifier: str) -> bool:
        """Check if request is allowed for this identifier."""
        with self.lock:
            if identifier not in self.limiters:
                self.limiters[identifier] = RateLimiter(
                    self.max_requests, self.window_seconds
                )
        return self.limiters[identifier].is_allowed()

    def get_status(self, identifier: str) -> Dict:
        """Get current quota status for an identifier."""
        with self.lock:
            if identifier not in self.limiters:
                return {
                    "remaining": self.max_requests,
                    "reset_seconds": 0.0,
                }
            limiter = self.limiters[identifier]

        return {
            "remaining": limiter.get_remaining(),
            "reset_seconds": limiter.get_reset_time(),
        }

# Single-limiter: 5 requests per 60 seconds
limiter = RateLimiter(max_requests=5, window_seconds=60)

if limiter.is_allowed():
    print("Request allowed")
else:
    wait_time = limiter.get_reset_time()
    print(f"Rate limited. Retry after {wait_time:.1f}s")

# Multi-key: different limits per user/IP
multi = MultiKeyRateLimiter(max_requests=100, window_seconds=3600)

if multi.is_allowed("user_123"):
    process_request()
else:
    status = multi.get_status("user_123")
    print(f"Reset in {status['reset_seconds']:.1f}s")