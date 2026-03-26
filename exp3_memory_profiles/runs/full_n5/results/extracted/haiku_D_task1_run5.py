import time
from collections import deque
from threading import Lock
from typing import Dict


class RateLimiter:
    """
    Sliding window rate limiter with exact timestamp tracking.
    Thread-safe for concurrent access.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        """
        Args:
            max_requests: Max requests allowed per window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = deque()  # Timestamps
        self.lock = Lock()

    def is_allowed(self) -> bool:
        """Check if request is allowed."""
        with self.lock:
            now = time.time()
            cutoff = now - self.window_seconds

            # Remove expired timestamps
            while self.requests and self.requests[0] < cutoff:
                self.requests.popleft()

            # Allow if under limit
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            return False

    def get_status(self) -> Dict[str, any]:
        """Return remaining requests and next reset time."""
        with self.lock:
            now = time.time()
            cutoff = now - self.window_seconds
            
            valid = sum(1 for ts in self.requests if ts >= cutoff)
            next_reset = self.requests[0] + self.window_seconds if self.requests else now

            return {
                "requests_in_window": valid,
                "remaining": max(0, self.max_requests - valid),
                "next_reset_seconds": max(0, next_reset - now),
            }


class MultiKeyRateLimiter:
    """Per-user/per-IP rate limiting."""

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.limiters: Dict[str, deque] = {}
        self.lock = Lock()

    def is_allowed(self, identifier: str) -> bool:
        """Check if request from identifier is allowed."""
        with self.lock:
            now = time.time()
            cutoff = now - self.window_seconds

            if identifier not in self.limiters:
                self.limiters[identifier] = deque()

            requests = self.limiters[identifier]
            while requests and requests[0] < cutoff:
                requests.popleft()

            if len(requests) < self.max_requests:
                requests.append(now)
                return True
            return False

    def get_status(self, identifier: str) -> Dict[str, any]:
        """Get status for specific identifier."""
        with self.lock:
            if identifier not in self.limiters:
                return {"requests_in_window": 0, "remaining": self.max_requests, "next_reset_seconds": 0}

            now = time.time()
            cutoff = now - self.window_seconds
            requests = self.limiters[identifier]
            
            valid = sum(1 for ts in requests if ts >= cutoff)
            next_reset = requests[0] + self.window_seconds if requests else now

            return {
                "requests_in_window": valid,
                "remaining": max(0, self.max_requests - valid),
                "next_reset_seconds": max(0, next_reset - now),
            }

# Single global limit (e.g., API service)
limiter = RateLimiter(max_requests=100, window_seconds=60)

if limiter.is_allowed():
    handle_request()
else:
    return 429  # Too Many Requests

# Per-user limits (e.g., auth'd API)
user_limiters = MultiKeyRateLimiter(max_requests=50, window_seconds=60)

if user_limiters.is_allowed(user_id):
    handle_request()
else:
    status = user_limiters.get_status(user_id)
    wait_seconds = status["next_reset_seconds"]
    return 429, {"retry_after": wait_seconds}