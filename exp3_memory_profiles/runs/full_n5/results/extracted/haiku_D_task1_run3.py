import time
from collections import deque
from threading import Lock
from typing import Optional


class RateLimiter:
    """
    Thread-safe rate limiter using a sliding window approach.

    Allows N requests within a fixed time window. Old timestamps are
    automatically cleaned up to prevent memory leaks.

    Args:
        max_requests: Maximum number of requests allowed per window
        window_seconds: Time window in seconds
    """

    def __init__(self, max_requests: int, window_seconds: float):
        if max_requests <= 0 or window_seconds <= 0:
            raise ValueError("max_requests and window_seconds must be positive")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: deque = deque()
        self._lock = Lock()

    def is_allowed(self, now: Optional[float] = None) -> bool:
        """Check if a request is allowed under the rate limit."""
        if now is None:
            now = time.time()

        with self._lock:
            # Remove timestamps outside the window
            cutoff = now - self.window_seconds
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()

            if len(self._timestamps) < self.max_requests:
                self._timestamps.append(now)
                return True
            return False

    def get_retry_after(self, now: Optional[float] = None) -> Optional[float]:
        """Get seconds to wait before next request can succeed."""
        if now is None:
            now = time.time()

        with self._lock:
            cutoff = now - self.window_seconds
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()

            if len(self._timestamps) < self.max_requests:
                return None

            oldest = self._timestamps[0]
            return oldest + self.window_seconds - now

    def reset(self) -> None:
        """Clear all tracked requests."""
        with self._lock:
            self._timestamps.clear()

    def current_count(self) -> int:
        """Get requests currently in the window."""
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            while self._timestamps and self._timestamps[0] < cutoff:
                self._timestamps.popleft()
            return len(self._timestamps)


# Test cases
if __name__ == "__main__":
    limiter = RateLimiter(max_requests=3, window_seconds=10)
    
    # Test 1: First 3 requests allowed
    assert limiter.is_allowed() == True
    assert limiter.is_allowed() == True
    assert limiter.is_allowed() == True
    print("✓ Test 1: First 3 requests allowed")
    
    # Test 2: 4th request denied
    assert limiter.is_allowed() == False
    print("✓ Test 2: 4th request denied")
    
    # Test 3: Retry-after returns time to wait
    retry_time = limiter.get_retry_after()
    assert retry_time is not None and 0 < retry_time <= 10
    print(f"✓ Test 3: Retry-after = {retry_time:.2f}s")
    
    # Test 4: Window reset allows new requests
    limiter.reset()
    assert limiter.is_allowed() == True
    assert limiter.current_count() == 1
    print("✓ Test 4: Reset works")
    
    # Test 5: Time-based window (simulated)
    limiter2 = RateLimiter(max_requests=2, window_seconds=1)
    assert limiter2.is_allowed(now=0.0) == True
    assert limiter2.is_allowed(now=0.1) == True
    assert limiter2.is_allowed(now=0.2) == False  # Window full
    assert limiter2.is_allowed(now=1.5) == True   # Old request expired
    print("✓ Test 5: Sliding window cleanup works")
    
    print("\nAll tests passed!")

import asyncio
# Replace: self._lock = Lock()
# With:    self._lock = asyncio.Lock()

import redis

class DistributedRateLimiter:
    def __init__(self, key: str, max_requests: int, window_seconds: int):
        self.redis = redis.Redis()
        self.key = key
        self.max_requests = max_requests
        self.window_seconds = window_seconds
    
    def is_allowed(self):
        now = time.time()
        pipe = self.redis.pipeline()
        pipe.zremrangebyscore(self.key, 0, now - self.window_seconds)
        pipe.zcard(self.key)
        pipe.zadd(self.key, {str(now): now})
        pipe.expire(self.key, self.window_seconds + 1)
        _, count, _, _ = pipe.execute()
        return count < self.max_requests