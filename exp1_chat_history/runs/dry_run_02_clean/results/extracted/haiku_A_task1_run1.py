from collections import deque
from time import time
from threading import Lock

class RateLimiter:
    """
    A sliding window rate limiter that tracks request timestamps.
    
    Allows N requests per time window. Requests outside the current
    time window are automatically discarded.
    """
    
    def __init__(self, max_requests: int, time_window_seconds: float):
        """
        Initialize the rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed
            time_window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window_seconds = time_window_seconds
        self.requests = deque()  # Stores request timestamps
        self.lock = Lock()  # Thread safety
    
    def _cleanup_old_requests(self) -> None:
        """Remove requests older than the time window."""
        cutoff_time = time() - self.time_window_seconds
        while self.requests and self.requests[0] < cutoff_time:
            self.requests.popleft()
    
    def is_allowed(self) -> bool:
        """
        Check if a request is allowed.
        
        Returns:
            True if the request is allowed, False otherwise
        """
        with self.lock:
            self._cleanup_old_requests()
            
            if len(self.requests) < self.max_requests:
                self.requests.append(time())
                return True
            return False
    
    def get_stats(self) -> dict:
        """
        Get current rate limiter statistics.
        
        Returns:
            Dictionary with request count and next available time
        """
        with self.lock:
            self._cleanup_old_requests()
            requests_count = len(self.requests)
            
            if self.requests:
                next_available = self.requests[0] + self.time_window_seconds
            else:
                next_available = time()
            
            return {
                "current_requests": requests_count,
                "max_requests": self.max_requests,
                "requests_remaining": self.max_requests - requests_count,
                "next_available_in_seconds": max(0, next_available - time())
            }


# Example usage
if __name__ == "__main__":
    import time as time_module
    
    # 5 requests per 10 seconds
    limiter = RateLimiter(max_requests=5, time_window_seconds=10)
    
    # Test: make 7 requests
    for i in range(7):
        allowed = limiter.is_allowed()
        stats = limiter.get_stats()
        print(f"Request {i+1}: {'✓ Allowed' if allowed else '✗ Rejected'} | Stats: {stats}")
    
    print("\nWaiting 3 seconds...\n")
    time_module.sleep(3)
    
    # After 3 seconds, the oldest request is still within the window
    for i in range(3):
        allowed = limiter.is_allowed()
        stats = limiter.get_stats()
        print(f"Request {i+8}: {'✓ Allowed' if allowed else '✗ Rejected'} | Stats: {stats}")