import time
from collections import deque
from threading import Lock
from typing import Optional


class RateLimiter:
    """
    A rate limiter using sliding window counter algorithm.
    Allows N requests per time window with thread-safe timestamp tracking.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        """
        Initialize the rate limiter.

        Args:
            max_requests: Maximum number of requests allowed in the time window
            window_seconds: Time window duration in seconds
        """
        if max_requests <= 0 or window_seconds <= 0:
            raise ValueError("max_requests and window_seconds must be positive")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = deque()  # Stores timestamps of requests
        self.lock = Lock()

    def is_allowed(self) -> bool:
        """
        Check if a request is allowed and record it if allowed.

        Returns:
            True if the request is allowed, False otherwise
        """
        with self.lock:
            current_time = time.time()

            # Remove timestamps outside the sliding window
            cutoff_time = current_time - self.window_seconds
            while self.requests and self.requests[0] < cutoff_time:
                self.requests.popleft()

            # Check if request is allowed
            if len(self.requests) < self.max_requests:
                self.requests.append(current_time)
                return True

            return False

    def get_status(self) -> dict:
        """Get current rate limiter status (remaining quota, reset time, etc.)"""
        with self.lock:
            current_time = time.time()

            # Clean old requests
            cutoff_time = current_time - self.window_seconds
            while self.requests and self.requests[0] < cutoff_time:
                self.requests.popleft()

            # Calculate reset time
            reset_in = None
            if self.requests:
                reset_in = max(0, self.requests[0] + self.window_seconds - current_time)

            return {
                "current_requests": len(self.requests),
                "max_requests": self.max_requests,
                "requests_remaining": max(0, self.max_requests - len(self.requests)),
                "reset_in_seconds": reset_in or 0
            }

    def reset(self) -> None:
        """Clear all tracked requests."""
        with self.lock:
            self.requests.clear()


# Usage example
if __name__ == "__main__":
    limiter = RateLimiter(max_requests=5, window_seconds=10)

    print("=== Testing Rate Limiter (5 requests per 10 seconds) ===\n")

    # Attempt 7 rapid requests
    for i in range(7):
        allowed = limiter.is_allowed()
        status = limiter.get_status()
        print(f"Request {i+1}: {'✓ ALLOWED' if allowed else '✗ DENIED'} | "
              f"Remaining: {status['requests_remaining']}")

    print(f"\nStatus: {limiter.get_status()}")

limiter = RateLimiter(max_requests=100, window_seconds=60)

if limiter.is_allowed():
    # Process request
    pass
else:
    # Return 429 Too Many Requests
    pass