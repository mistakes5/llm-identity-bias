import time
from collections import defaultdict
from threading import Lock
from typing import Dict, List, Optional


class RateLimiter:
    """
    A thread-safe rate limiter using a sliding window approach.

    Tracks request timestamps and allows up to N requests per time window.
    Requests older than the time window are automatically pruned.
    """

    def __init__(self, max_requests: int, time_window: float):
        """
        Initialize the rate limiter.

        Args:
            max_requests: Maximum number of requests allowed in the time window
            time_window: Time window in seconds (e.g., 60 for per-minute, 3600 for per-hour)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self._requests: Dict[str, List[float]] = defaultdict(list)
        self._lock = Lock()

    def is_allowed(self, identifier: str = "default") -> bool:
        """
        Check if a request is allowed for the given identifier.

        Args:
            identifier: Unique identifier for the requester (e.g., IP, user_id)
                       Defaults to "default" for single-client use

        Returns:
            True if the request is allowed, False if rate limit exceeded
        """
        current_time = time.time()

        with self._lock:
            # Get existing request timestamps for this identifier
            requests = self._requests[identifier]

            # Remove timestamps outside the time window
            cutoff_time = current_time - self.time_window
            requests[:] = [ts for ts in requests if ts > cutoff_time]

            # Check if we're under the limit
            if len(requests) < self.max_requests:
                requests.append(current_time)
                return True

            return False

    def get_remaining_requests(self, identifier: str = "default") -> int:
        """Get the number of remaining requests allowed."""
        current_time = time.time()

        with self._lock:
            requests = self._requests[identifier]
            cutoff_time = current_time - self.time_window
            active_requests = [ts for ts in requests if ts > cutoff_time]
            return max(0, self.max_requests - len(active_requests))

    def reset(self, identifier: Optional[str] = None) -> None:
        """Reset rate limit history for an identifier or all identifiers."""
        with self._lock:
            if identifier is None:
                self._requests.clear()
            elif identifier in self._requests:
                del self._requests[identifier]

# Simple: 5 requests per 10 seconds
limiter = RateLimiter(max_requests=5, time_window=10)

# Check a request
if limiter.is_allowed("user_123"):
    print("Request allowed")
else:
    print("Rate limit exceeded")

# Get remaining quota
remaining = limiter.get_remaining_requests("user_123")

# Reset for a specific user or all users
limiter.reset("user_123")  # Single user
limiter.reset()             # All users