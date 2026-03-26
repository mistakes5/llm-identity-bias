import time
from collections import deque
from abc import ABC, abstractmethod
from typing import Optional
from threading import Lock


class RateLimiter(ABC):
    @abstractmethod
    def is_allowed(self) -> bool:
        pass

    @abstractmethod
    def get_retry_after(self) -> Optional[float]:
        """Seconds until next request allowed."""
        pass


class FixedWindowRateLimiter(RateLimiter):
    """Resets counter at fixed intervals. Fast, allows bursts at boundaries."""
    
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

    def get_retry_after(self) -> Optional[float]:
        with self.lock:
            now = time.time()
            elapsed = now - self.window_start
            if elapsed >= self.window_seconds:
                return 0.0
            return self.window_seconds - elapsed if self.request_count >= self.max_requests else 0.0


class SlidingWindowRateLimiter(RateLimiter):
    """Tracks individual timestamps. Prevents boundary bursts, O(N) memory."""
    
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.timestamps = deque()
        self.lock = Lock()

    def is_allowed(self) -> bool:
        with self.lock:
            now = time.time()
            cutoff = now - self.window_seconds
            
            while self.timestamps and self.timestamps[0] < cutoff:
                self.timestamps.popleft()

            if len(self.timestamps) < self.max_requests:
                self.timestamps.append(now)
                return True
            return False

    def get_retry_after(self) -> Optional[float]:
        with self.lock:
            now = time.time()
            cutoff = now - self.window_seconds
            
            while self.timestamps and self.timestamps[0] < cutoff:
                self.timestamps.popleft()

            if len(self.timestamps) < self.max_requests:
                return 0.0
            
            return self.timestamps[0] + self.window_seconds - now if self.timestamps else 0.0


class TokenBucketRateLimiter(RateLimiter):
    """Refills tokens at constant rate. Allows bursts, enforces average rate."""
    
    def __init__(self, max_tokens: int, refill_rate: float):
        """
        Args:
            max_tokens: Burst capacity
            refill_rate: Tokens per second
        """
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self.tokens = max_tokens
        self.last_refill = time.time()
        self.lock = Lock()

    def _refill(self, now: float) -> None:
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    def is_allowed(self, tokens_required: int = 1) -> bool:
        with self.lock:
            self._refill(time.time())
            if self.tokens >= tokens_required:
                self.tokens -= tokens_required
                return True
            return False

    def get_retry_after(self, tokens_required: int = 1) -> Optional[float]:
        with self.lock:
            self._refill(time.time())
            if self.tokens >= tokens_required:
                return 0.0
            tokens_needed = tokens_required - self.tokens
            return tokens_needed / self.refill_rate