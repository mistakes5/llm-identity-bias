"""
Rate Limiter: Sliding window implementation supporting N requests per time window.

Two strategies included:
1. SlidingWindowRateLimiter - Precise, memory-efficient (using deque)
2. FixedWindowRateLimiter - Simpler, slightly less precise (resets at intervals)
"""

import time
from collections import deque
from typing import Dict
from threading import Lock


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter using a deque of timestamps.

    Allows up to `max_requests` within a rolling `window_seconds` interval.
    More precise than fixed windows but slightly higher memory overhead.

    Example:
        limiter = SlidingWindowRateLimiter(max_requests=10, window_seconds=60)
        if limiter.is_allowed("user_123"):
            process_request()
    """

    def __init__(self, max_requests: int, window_seconds: float):
        """
        Args:
            max_requests: Maximum number of requests allowed per window
            window_seconds: Time window in seconds (e.g., 60 for per-minute limits)
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, deque] = {}
        self.lock = Lock()

    def is_allowed(self, identifier: str) -> bool:
        """
        Check if a request is allowed for the given identifier.

        Args:
            identifier: Unique key (e.g., user_id, IP address, API key)

        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        current_time = time.time()

        with self.lock:
            # Initialize deque if first request from this identifier
            if identifier not in self.requests:
                self.requests[identifier] = deque()

            request_times = self.requests[identifier]

            # Remove timestamps outside the current window
            window_start = current_time - self.window_seconds
            while request_times and request_times[0] < window_start:
                request_times.popleft()

            # Check if under limit
            if len(request_times) < self.max_requests:
                request_times.append(current_time)
                return True

            return False

    def get_remaining(self, identifier: str) -> int:
        """Get remaining requests for this identifier in current window."""
        current_time = time.time()

        with self.lock:
            if identifier not in self.requests:
                return self.max_requests

            request_times = self.requests[identifier]
            window_start = current_time - self.window_seconds

            # Count valid requests in window
            valid_count = sum(1 for t in request_times if t >= window_start)
            return max(0, self.max_requests - valid_count)

    def reset(self, identifier: str = None) -> None:
        """
        Reset rate limit for an identifier. If identifier is None, reset all.
        """
        with self.lock:
            if identifier:
                self.requests.pop(identifier, None)
            else:
                self.requests.clear()


class FixedWindowRateLimiter:
    """
    Fixed window rate limiter (simpler, slightly less precise).

    Resets the request counter at fixed intervals. Simpler than sliding window
    but vulnerable to "burst at window boundary" attacks (user can make 2x requests
    by requesting just before and after a window reset).

    Use SlidingWindowRateLimiter for production APIs; use this for simpler scenarios.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        """
        Args:
            max_requests: Maximum requests per window
            window_seconds: Duration of each fixed window
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.request_counts: Dict[str, tuple[int, float]] = {}  # {id: (count, window_start)}
        self.lock = Lock()

    def is_allowed(self, identifier: str) -> bool:
        """Check if request is allowed within current fixed window."""
        current_time = time.time()
        current_window = int(current_time / self.window_seconds)

        with self.lock:
            if identifier not in self.request_counts:
                self.request_counts[identifier] = (1, current_window)
                return True

            count, window = self.request_counts[identifier]

            # New window started, reset counter
            if window != current_window:
                self.request_counts[identifier] = (1, current_window)
                return True

            # Still in same window
            if count < self.max_requests:
                self.request_counts[identifier] = (count + 1, window)
                return True

            return False

    def reset(self, identifier: str = None) -> None:
        """Reset rate limit for an identifier."""
        with self.lock:
            if identifier:
                self.request_counts.pop(identifier, None)
            else:
                self.request_counts.clear()


# Example usage
if __name__ == "__main__":
    # Sliding window: 5 requests per 10 seconds
    limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=10)
    
    for i in range(7):
        allowed = limiter.is_allowed("user_123")
        remaining = limiter.get_remaining("user_123")
        print(f"Request {i+1}: {'✓ ALLOWED' if allowed else '✗ BLOCKED'} "
              f"(Remaining: {remaining})")

# Web API rate limiting
api_limiter = SlidingWindowRateLimiter(max_requests=100, window_seconds=60)

if api_limiter.is_allowed(user_id):
    # Process request
    pass
else:
    # Return 429 Too Many Requests
    return error_response(429)

# Show remaining quota
remaining = api_limiter.get_remaining(user_id)
set_header('X-RateLimit-Remaining', remaining)

# Manual reset (e.g., after user upgrades plan)
api_limiter.reset(user_id)