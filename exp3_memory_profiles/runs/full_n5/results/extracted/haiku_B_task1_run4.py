from collections import deque
from time import time
from typing import Optional, Dict


class RateLimiter:
    """
    A rate limiter using sliding window log algorithm.
    Allows N requests per time window with precise timestamp tracking.
    """

    def __init__(self, max_requests: int, time_window: float):
        """
        Initialize the rate limiter.

        Args:
            max_requests: Maximum number of requests allowed in the window
            time_window: Time window duration in seconds
        """
        if max_requests <= 0 or time_window <= 0:
            raise ValueError("max_requests and time_window must be positive")

        self.max_requests = max_requests
        self.time_window = time_window
        self.request_times: deque = deque()

    def is_allowed(self) -> bool:
        """
        Check if a request is allowed and record it if permitted.

        Returns:
            True if request is allowed (within limits), False otherwise
        """
        now = time()

        # Remove expired requests outside the time window
        while self.request_times and self.request_times[0] <= now - self.time_window:
            self.request_times.popleft()

        # Check if we have capacity
        if len(self.request_times) < self.max_requests:
            self.request_times.append(now)
            return True

        return False

    def get_remaining_requests(self) -> int:
        """Get remaining requests available in the current window."""
        now = time()
        while self.request_times and self.request_times[0] <= now - self.time_window:
            self.request_times.popleft()
        return max(0, self.max_requests - len(self.request_times))

    def get_reset_time(self) -> Optional[float]:
        """Get seconds until rate limit resets."""
        if not self.request_times:
            return None

        oldest_request = self.request_times[0]
        reset_time = oldest_request + self.time_window - time()
        return max(0.0, reset_time)

    def reset(self) -> None:
        """Clear all tracked requests."""
        self.request_times.clear()

    def __repr__(self) -> str:
        return (
            f"RateLimiter(max_requests={self.max_requests}, "
            f"time_window={self.time_window}s, "
            f"current_requests={len(self.request_times)})"
        )


class MultiUserRateLimiter:
    """Rate limiter for multiple users with per-user limits."""

    def __init__(self, max_requests: int, time_window: float):
        self.max_requests = max_requests
        self.time_window = time_window
        self.limiters: Dict[str, RateLimiter] = {}

    def is_allowed(self, user_id: str) -> bool:
        """Check if a user's request is allowed."""
        if user_id not in self.limiters:
            self.limiters[user_id] = RateLimiter(self.max_requests, self.time_window)

        return self.limiters[user_id].is_allowed()

    def get_remaining_requests(self, user_id: str) -> int:
        """Get remaining requests for a specific user."""
        if user_id not in self.limiters:
            return self.max_requests
        return self.limiters[user_id].get_remaining_requests()

    def reset_user(self, user_id: str) -> None:
        """Reset rate limit for a specific user."""
        if user_id in self.limiters:
            self.limiters[user_id].reset()

# Single-user rate limiter: 5 requests per 10 seconds
limiter = RateLimiter(max_requests=5, time_window=10.0)

# Check requests
for i in range(7):
    allowed = limiter.is_allowed()
    remaining = limiter.get_remaining_requests()
    print(f"Request {i+1}: {'✓ Allowed' if allowed else '✗ Blocked'} ({remaining} remaining)")

# Multi-user rate limiter
multi_limiter = MultiUserRateLimiter(max_requests=3, time_window=60.0)

if multi_limiter.is_allowed("user_123"):
    print("User 123 request allowed")
remaining = multi_limiter.get_remaining_requests("user_123")
print(f"User 123 has {remaining} requests left")