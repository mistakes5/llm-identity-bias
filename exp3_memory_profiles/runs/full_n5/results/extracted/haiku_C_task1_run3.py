"""
Rate Limiter Implementation with Multiple Strategies
"""

import time
from collections import deque
from typing import Dict
from threading import Lock
from abc import ABC, abstractmethod


class RateLimiter(ABC):
    """Abstract base class for rate limiting strategies."""

    @abstractmethod
    def is_allowed(self, identifier: str) -> bool:
        """Check if a request is allowed for the given identifier."""
        pass

    @abstractmethod
    def get_remaining(self, identifier: str) -> int:
        """Get remaining requests for the identifier."""
        pass


class SlidingWindowRateLimiter(RateLimiter):
    """
    Sliding Window Counter - Most accurate approach.
    
    Tracks individual request timestamps within the current time window.
    Provides precise rate limiting but requires storing all recent timestamps.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, deque] = {}
        self.lock = Lock()

    def is_allowed(self, identifier: str) -> bool:
        with self.lock:
            current_time = time.time()
            window_start = current_time - self.window_seconds

            if identifier not in self.requests:
                self.requests[identifier] = deque()

            request_times = self.requests[identifier]

            # Remove timestamps outside the window
            while request_times and request_times[0] < window_start:
                request_times.popleft()

            if len(request_times) < self.max_requests:
                request_times.append(current_time)
                return True
            return False

    def get_remaining(self, identifier: str) -> int:
        with self.lock:
            current_time = time.time()
            window_start = current_time - self.window_seconds

            if identifier not in self.requests:
                return self.max_requests

            request_times = self.requests[identifier]
            valid_requests = sum(
                1 for ts in request_times
                if ts >= window_start
            )
            return max(0, self.max_requests - valid_requests)


class TokenBucketRateLimiter(RateLimiter):
    """
    Token Bucket - Allows controlled bursts.
    
    Tokens accumulate at a constant rate. Each request consumes one token.
    Great for APIs that should allow temporary spikes while maintaining 
    average rate limits.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        self.max_tokens = max_requests
        self.refill_rate = max_requests / window_seconds  # tokens/second
        self.buckets: Dict[str, Dict] = {}
        self.lock = Lock()

    def is_allowed(self, identifier: str) -> bool:
        with self.lock:
            current_time = time.time()

            if identifier not in self.buckets:
                self.buckets[identifier] = {
                    "tokens": self.max_tokens,
                    "last_refill": current_time,
                }

            bucket = self.buckets[identifier]
            elapsed = current_time - bucket["last_refill"]
            bucket["tokens"] = min(
                self.max_tokens,
                bucket["tokens"] + elapsed * self.refill_rate,
            )
            bucket["last_refill"] = current_time

            if bucket["tokens"] >= 1:
                bucket["tokens"] -= 1
                return True
            return False

    def get_remaining(self, identifier: str) -> int:
        with self.lock:
            if identifier not in self.buckets:
                return self.max_tokens
            bucket = self.buckets[identifier]
            elapsed = time.time() - bucket["last_refill"]
            tokens = min(
                self.max_tokens,
                bucket["tokens"] + elapsed * self.refill_rate,
            )
            return int(tokens)

# Example usage and testing
if __name__ == "__main__":
    # Create a rate limiter: 5 requests per 10 seconds
    limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=10)
    
    # Simulate requests from a user
    user_id = "user_123"
    
    print("Testing Sliding Window Rate Limiter (5 requests/10s):")
    for i in range(7):
        allowed = limiter.is_allowed(user_id)
        remaining = limiter.get_remaining(user_id)
        print(f"Request {i+1}: {'✓ Allowed' if allowed else '✗ Blocked'} "
              f"(Remaining: {remaining})")
    
    # Test with Token Bucket
    print("\nTesting Token Bucket (10 requests/60s):")
    token_limiter = TokenBucketRateLimiter(max_requests=10, window_seconds=60)
    
    for i in range(12):
        allowed = token_limiter.is_allowed(user_id)
        remaining = token_limiter.get_remaining(user_id)
        print(f"Request {i+1}: {'✓ Allowed' if allowed else '✗ Blocked'} "
              f"(Remaining: {remaining})")