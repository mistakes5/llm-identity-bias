"""
Rate limiter implementation with multiple strategies.

Supports:
- Sliding window counter (accurate, memory-efficient)
- Fixed window counter (simple, allows burst at boundaries)
- Token bucket (smooth rate limiting, allows bursts)
"""

import time
from collections import deque
from typing import Optional, Dict
from threading import Lock


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter - tracks exact request timestamps.
    
    Best for: API rate limiting, accurate enforcement
    """
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.request_timestamps: deque = deque()
        self.lock = Lock()

    def is_allowed(self) -> bool:
        with self.lock:
            now = time.time()
            # Remove timestamps outside the current window
            while self.request_timestamps and \
                  self.request_timestamps[0] < now - self.window_seconds:
                self.request_timestamps.popleft()

            if len(self.request_timestamps) < self.max_requests:
                self.request_timestamps.append(now)
                return True
            return False

    def get_request_count(self) -> int:
        with self.lock:
            now = time.time()
            while self.request_timestamps and \
                  self.request_timestamps[0] < now - self.window_seconds:
                self.request_timestamps.popleft()
            return len(self.request_timestamps)

    def get_reset_time(self) -> Optional[float]:
        with self.lock:
            if not self.request_timestamps or \
               len(self.request_timestamps) < self.max_requests:
                return 0
            oldest = self.request_timestamps[0]
            reset_time = oldest + self.window_seconds - time.time()
            return max(0, reset_time)


class FixedWindowRateLimiter:
    """
    Fixed window rate limiter - resets counter at fixed intervals.
    
    Best for: Simple rate limiting, minimal memory overhead
    """
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.request_count = 0
        self.window_start = time.time()
        self.lock = Lock()

    def is_allowed(self) -> bool:
        with self.lock:
            now = time.time()
            if now - self.window_start >= self.window_seconds:
                self.window_start = now
                self.request_count = 0

            if self.request_count < self.max_requests:
                self.request_count += 1
                return True
            return False

    def get_request_count(self) -> int:
        with self.lock:
            now = time.time()
            if now - self.window_start >= self.window_seconds:
                return 0
            return self.request_count

    def get_reset_time(self) -> float:
        with self.lock:
            reset_time = self.window_start + self.window_seconds - time.time()
            return max(0, reset_time)


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter - smooth rate limiting with burst capacity.
    
    Best for: Allowing occasional bursts within overall rate limit
    """
    def __init__(self, max_requests: int, window_seconds: float, 
                 burst_size: Optional[int] = None):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.burst_size = burst_size or max_requests
        self.tokens = self.burst_size
        self.last_update = time.time()
        self.lock = Lock()

    def is_allowed(self, tokens_required: int = 1) -> bool:
        with self.lock:
            self._refill()
            if self.tokens >= tokens_required:
                self.tokens -= tokens_required
                return True
            return False

    def _refill(self):
        now = time.time()
        elapsed = now - self.last_update
        tokens_to_add = (elapsed / self.window_seconds) * self.max_requests
        self.tokens = min(self.burst_size, self.tokens + tokens_to_add)
        self.last_update = now

    def get_available_tokens(self) -> float:
        with self.lock:
            self._refill()
            return self.tokens


class KeyedRateLimiter:
    """Rate limiter maintaining separate limits per key (e.g., IP address)."""

    def __init__(self, max_requests: int, window_seconds: float,
                 limiter_class=SlidingWindowRateLimiter):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.limiter_class = limiter_class
        self.limiters: Dict[str, object] = {}
        self.lock = Lock()

    def is_allowed(self, key: str) -> bool:
        with self.lock:
            if key not in self.limiters:
                self.limiters[key] = self.limiter_class(
                    self.max_requests, self.window_seconds
                )
            return self.limiters[key].is_allowed()

    def cleanup_expired(self, inactive_seconds: float = 3600):
        with self.lock:
            now = time.time()
            expired_keys = [
                key for key, limiter in self.limiters.items()
                if hasattr(limiter, 'request_timestamps') and
                limiter.request_timestamps and
                limiter.request_timestamps[-1] < now - inactive_seconds
            ]
            for key in expired_keys:
                del self.limiters[key]
            return len(expired_keys)

# 5 requests per 10 seconds
limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=10)

if limiter.is_allowed():
    process_request()
else:
    return 429, f"Rate limited. Reset in {limiter.get_reset_time():.1f}s"

# Per-IP rate limiting
keyed_limiter = KeyedRateLimiter(max_requests=10, window_seconds=60)
if keyed_limiter.is_allowed(client_ip):
    process_request()