from time import time
from collections import deque
from threading import Lock

class SlidingWindowRateLimiter:
    """Most accurate - allows N requests per sliding time window."""
    
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = deque()  # Stores request timestamps
        self.lock = Lock()
    
    def is_allowed(self) -> bool:
        """Returns True if request is allowed, False otherwise."""
        with self.lock:
            now = time()
            cutoff = now - self.window_seconds
            
            # Remove timestamps older than the window
            while self.requests and self.requests[0] < cutoff:
                self.requests.popleft()
            
            # Check if under limit
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            return False
    
    def get_request_count(self) -> int:
        """Get current requests in the active window."""
        with self.lock:
            now = time()
            return sum(1 for ts in self.requests 
                      if ts >= now - self.window_seconds)

class TokenBucketRateLimiter:
    """Flexible - allows bursts when tokens available."""
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Args:
            capacity: Max tokens (burst size, e.g., 10)
            refill_rate: Tokens per second (e.g., 2 = 2 req/sec sustained)
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time()
        self.lock = Lock()
    
    def is_allowed(self, tokens_required: int = 1) -> bool:
        """Check if enough tokens available."""
        with self.lock:
            now = time()
            elapsed = now - self.last_refill
            
            # Add tokens based on time elapsed
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.refill_rate
            )
            self.last_refill = now
            
            # Deduct if enough
            if self.tokens >= tokens_required:
                self.tokens -= tokens_required
                return True
            return False

class FixedWindowRateLimiter:
    """Simple bucketing - O(1) check, artificial resets."""
    
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.window_start = time()
        self.request_count = 0
        self.lock = Lock()
    
    def is_allowed(self) -> bool:
        with self.lock:
            now = time()
            
            # New window?
            if now - self.window_start >= self.window_seconds:
                self.window_start = now
                self.request_count = 0
            
            if self.request_count < self.max_requests:
                self.request_count += 1
                return True
            return False

class MultiUserRateLimiter:
    """Track per-user, per-IP, or per-API-key limits."""
    
    def __init__(self, max_requests: int, window_seconds: float):
        self.limiters = {}  # {identifier: SlidingWindowRateLimiter}
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.lock = Lock()
    
    def is_allowed(self, identifier: str) -> bool:
        """identifier = user_id, IP address, API key, etc."""
        with self.lock:
            if identifier not in self.limiters:
                self.limiters[identifier] = SlidingWindowRateLimiter(
                    self.max_requests, self.window_seconds
                )
            return self.limiters[identifier].is_allowed()
    
    def get_status(self, identifier: str) -> dict:
        """Return remaining quota."""
        with self.lock:
            if identifier not in self.limiters:
                return {"remaining": self.max_requests}
            
            used = self.limiters[identifier].get_request_count()
            return {"remaining": self.max_requests - used}