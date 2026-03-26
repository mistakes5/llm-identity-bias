import time
from collections import defaultdict
from threading import Lock
from typing import Optional


class RateLimiter:
    """
    A thread-safe rate limiter that tracks N requests per time window.
    
    Uses a sliding window counter approach: tracks actual request timestamps
    and allows a request only if the number of requests in the current window
    is below the limit.
    """

    def __init__(self, max_requests: int, window_seconds: float):
        """Initialize the rate limiter with max requests and time window."""
        if max_requests <= 0:
            raise ValueError("max_requests must be greater than 0")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be greater than 0")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        
        # Store request timestamps per identifier
        # {identifier: [timestamp1, timestamp2, ...]}
        self._requests: defaultdict[str, list[float]] = defaultdict(list)
        
        # Lock for thread-safe access
        self._lock = Lock()

    def _cleanup_expired(self, identifier: str) -> None:
        """Remove timestamps outside the current time window."""
        now = time.time()
        cutoff_time = now - self.window_seconds
        
        self._requests[identifier] = [
            ts for ts in self._requests[identifier]
            if ts > cutoff_time
        ]

    def is_allowed(self, identifier: str) -> bool:
        """Check if request is allowed WITHOUT recording it."""
        with self._lock:
            self._cleanup_expired(identifier)
            return len(self._requests[identifier]) < self.max_requests

    def check_request(self, identifier: str) -> bool:
        """Check if request is allowed AND record it if accepted."""
        with self._lock:
            self._cleanup_expired(identifier)
            
            if len(self._requests[identifier]) < self.max_requests:
                self._requests[identifier].append(time.time())
                return True
            
            return False

    def get_request_count(self, identifier: str) -> int:
        """Get current request count within the window."""
        with self._lock:
            self._cleanup_expired(identifier)
            return len(self._requests[identifier])

    def reset(self, identifier: Optional[str] = None) -> None:
        """Reset request history for identifier or all identifiers."""
        with self._lock:
            if identifier is None:
                self._requests.clear()
            elif identifier in self._requests:
                del self._requests[identifier]

    def get_remaining_requests(self, identifier: str) -> int:
        """Get number of remaining requests allowed."""
        return self.max_requests - self.get_request_count(identifier)


# Usage Example
if __name__ == "__main__":
    limiter = RateLimiter(max_requests=5, window_seconds=60)
    
    # Check and record a request
    if limiter.check_request("user_123"):
        print("Request allowed")
    else:
        print("Rate limit exceeded")
    
    # Check without recording
    if limiter.is_allowed("user_123"):
        print("User can make another request")
    
    print(f"Remaining: {limiter.get_remaining_requests('user_123')}")