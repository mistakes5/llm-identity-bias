import time
from collections import defaultdict

class RateLimiter:
    """
    Limits the number of requests allowed within a specific time window.
    Example: Allow 5 requests every 60 seconds per user
    """

    def __init__(self, max_requests, time_window_seconds):
        """
        Initialize the rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed (e.g., 5)
            time_window_seconds: The time period in seconds (e.g., 60)
        """
        # Store the limits
        self.max_requests = max_requests
        self.time_window_seconds = time_window_seconds

        # Dictionary to store request timestamps for each client/user
        # Key: client ID (string like "user123")
        # Value: list of timestamps (numbers from time.time())
        self.request_timestamps = defaultdict(list)

    def is_request_allowed(self, client_id):
        """
        Check if a request from a client is allowed.
        This is where the core logic goes!
        """
        current_time = time.time()
        cutoff_time = current_time - self.time_window_seconds
        
        # TODO: Implement this function
        # Step 1: Keep only recent timestamps (older than cutoff_time should be removed)
        # Step 2: Check if we have room for another request
        # Step 3: Return True if allowed, False if rate limited
        pass

    def add_request(self, client_id):
        """Record a request from a client."""
        current_time = time.time()
        self.request_timestamps[client_id].append(current_time)