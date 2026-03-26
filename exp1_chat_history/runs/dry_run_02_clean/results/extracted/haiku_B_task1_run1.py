from collections import deque
from time import time
from threading import Lock
from typing import Optional

class SlidingWindowRateLimiter:
    """
    Rate limiter using sliding window log approach.
    
    Tracks actual request timestamps within a time window.
    Most accurate but uses more memory for high request volumes.
    """
    
    def __init__(self, max_requests: int, window_seconds: float):
        """
        Initialize the rate limiter.
        
        Args:
            max_requests: Number of requests allowed per window
            window_seconds: Time window duration in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = deque()  # Store request timestamps
        self.lock = Lock()
    
    def is_allowed(self) -> bool:
        """
        Check if a request is allowed and record it if so.
        
        Returns:
            True if the request is within limits, False otherwise
        """
        with self.lock:
            now = time()
            
            # Remove timestamps outside the window
            cutoff = now - self.window_seconds
            while self.requests and self.requests[0] < cutoff:
                self.requests.popleft()
            
            # Check if we have room for another request
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            
            return False
    
    def get_retry_after(self) -> Optional[float]:
        """
        Get seconds to wait before next request is allowed.
        
        Returns:
            Seconds to wait, or None if request is allowed
        """
        with self.lock:
            if not self.requests:
                return None
            
            now = time()
            # Oldest request in window determines retry time
            oldest = self.requests[0]
            retry_after = max(0, (oldest + self.window_seconds) - now)
            
            return retry_after if retry_after > 0 else None
    
    def reset(self):
        """Clear all recorded requests."""
        with self.lock:
            self.requests.clear()


class TokenBucketRateLimiter:
    """
    Rate limiter using token bucket algorithm.
    
    Generates tokens over time. More flexible for burst traffic
    while maintaining average rate.
    """
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket rate limiter.
        
        Args:
            capacity: Maximum tokens in bucket
            refill_rate: Tokens generated per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time()
        self.lock = Lock()
    
    def _refill(self):
        """Refill bucket based on elapsed time."""
        now = time()
        elapsed = now - self.last_refill
        
        # Add tokens based on elapsed time
        new_tokens = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_refill = now
    
    def is_allowed(self, tokens_required: int = 1) -> bool:
        """
        Check if tokens are available and consume them if so.
        
        Args:
            tokens_required: Number of tokens needed (default 1)
        
        Returns:
            True if tokens available, False otherwise
        """
        with self.lock:
            self._refill()
            
            if self.tokens >= tokens_required:
                self.tokens -= tokens_required
                return True
            
            return False
    
    def get_retry_after(self) -> float:
        """
        Get seconds to wait for one token to become available.
        
        Returns:
            Seconds to wait
        """
        with self.lock:
            self._refill()
            
            if self.tokens >= 1:
                return 0.0
            
            # Time to generate one token
            tokens_needed = 1 - self.tokens
            return tokens_needed / self.refill_rate


# Example usage and testing
if __name__ == "__main__":
    import time as time_module
    
    print("=== Sliding Window Limiter (5 requests per 10 seconds) ===")
    limiter = SlidingWindowRateLimiter(max_requests=5, window_seconds=10)
    
    # Simulate 7 requests
    for i in range(7):
        allowed = limiter.is_allowed()
        print(f"Request {i+1}: {'✓ Allowed' if allowed else '✗ Blocked'}")
        if not allowed:
            retry = limiter.get_retry_after()
            print(f"  Retry after {retry:.2f}s")
    
    print("\n=== Token Bucket Limiter (10 tokens, 2 tokens/sec) ===")
    bucket = TokenBucketRateLimiter(capacity=10, refill_rate=2)
    
    # Consume tokens
    for i in range(12):
        allowed = bucket.is_allowed()
        print(f"Request {i+1}: {'✓ Allowed' if allowed else '✗ Blocked'}")
    
    # Wait for refill and retry
    print("\nWaiting 3 seconds for tokens to refill...")
    time_module.sleep(3)
    
    for i in range(3):
        allowed = bucket.is_allowed()
        print(f"Request {i+13}: {'✓ Allowed' if allowed else '✗ Blocked'}")