from collections import deque
from time import time
from threading import Lock
from typing import Dict, Tuple

class RateLimiter:
    """Fixed window counter approach - simple and efficient"""
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, Tuple[int, float]] = {}
        self.lock = Lock()
    
    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed for this client"""
        with self.lock:
            now = time()
            
            # Get current window info for this client
            if client_id not in self.requests:
                self.requests[client_id] = (1, now)
                return True
            
            count, window_start = self.requests[client_id]
            
            # Window has expired, reset counter
            if now - window_start >= self.window_seconds:
                self.requests[client_id] = (1, now)
                return True
            
            # Still in current window
            if count < self.max_requests:
                self.requests[client_id] = (count + 1, window_start)
                return True
            
            return False


class SlidingWindowRateLimiter:
    """Sliding window log approach - more accurate"""
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, deque] = {}
        self.lock = Lock()
    
    def is_allowed(self, client_id: str) -> bool:
        """Check if request is allowed using sliding window"""
        with self.lock:
            now = time()
            
            if client_id not in self.requests:
                self.requests[client_id] = deque([now])
                return True
            
            window = self.requests[client_id]
            
            # Remove timestamps outside current window
            while window and window[0] < now - self.window_seconds:
                window.popleft()
            
            # Check if under limit
            if len(window) < self.max_requests:
                window.append(now)
                return True
            
            return False


# Example usage
if __name__ == "__main__":
    # Allow 5 requests per 60 seconds
    limiter = RateLimiter(max_requests=5, window_seconds=60)
    
    # Test with a client
    for i in range(8):
        allowed = limiter.is_allowed("user_123")
        print(f"Request {i+1}: {'✓ Allowed' if allowed else '✗ Blocked'}")
    
    print("\n--- Sliding Window Example ---")
    sliding_limiter = SlidingWindowRateLimiter(max_requests=3, window_seconds=10)
    
    for i in range(5):
        allowed = sliding_limiter.is_allowed("api_client")
        print(f"Request {i+1}: {'✓ Allowed' if allowed else '✗ Blocked'}")