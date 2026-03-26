import time
from collections import defaultdict, deque
from threading import Lock
from typing import Dict, Deque, Tuple


class SlidingWindowRateLimiter:
    """Most accurate. Tracks exact timestamps."""
    
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, Deque[float]] = defaultdict(deque)
        self.lock = Lock()

    def is_allowed(self, identifier: str) -> bool:
        now = time.time()
        with self.lock:
            # Remove stale timestamps
            cutoff = now - self.window_seconds
            while self.requests[identifier] and self.requests[identifier][0] <= cutoff:
                self.requests[identifier].popleft()
            
            if len(self.requests[identifier]) < self.max_requests:
                self.requests[identifier].append(now)
                return True
            return False

    def get_state(self, identifier: str) -> Tuple[int, float]:
        """Returns (count, seconds_until_reset)."""
        with self.lock:
            now = time.time()
            cutoff = now - self.window_seconds
            while self.requests[identifier] and self.requests[identifier][0] <= cutoff:
                self.requests[identifier].popleft()
            
            count = len(self.requests[identifier])
            if not self.requests[identifier]:
                return (count, 0.0)
            
            reset_at = self.requests[identifier][0] + self.window_seconds
            return (count, max(0, reset_at - now))


class TokenBucketRateLimiter:
    """Handles bursts. Tokens refill at constant rate."""
    
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.refill_rate = max_requests / window_seconds
        self.buckets: Dict[str, list] = defaultdict(
            lambda: [float(self.max_requests), time.time()]
        )
        self.lock = Lock()

    def is_allowed(self, identifier: str, tokens: float = 1.0) -> bool:
        with self.lock:
            now = time.time()
            tokens_available, last_refill = self.buckets[identifier]
            
            elapsed = now - last_refill
            tokens_available = min(
                self.max_requests,
                tokens_available + (elapsed * self.refill_rate)
            )
            
            if tokens_available >= tokens:
                self.buckets[identifier][0] = tokens_available - tokens
                self.buckets[identifier][1] = now
                return True
            
            self.buckets[identifier][0] = tokens_available
            self.buckets[identifier][1] = now
            return False