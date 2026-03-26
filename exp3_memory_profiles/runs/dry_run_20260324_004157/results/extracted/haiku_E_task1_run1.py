import time
from collections import deque

class RateLimiter:
    """
    A simple rate limiter using the sliding window approach.
    """

    def __init__(self, max_requests, time_window):
        """
        Initialize the rate limiter.
        
        Args:
            max_requests: Maximum number of requests allowed per time window
            time_window: Time window duration in seconds (e.g., 60 for 1 minute)
        """
        self.max_requests = max_requests
        self.time_window = time_window
        # deque (double-ended queue) is perfect for this - fast at both ends
        self.request_timestamps = deque()

    def is_allowed(self):
        """
        Check if a request is allowed under the rate limit.
        
        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        # Get current time in seconds since epoch
        current_time = time.time()

        # Calculate cutoff time - anything older than this gets ignored
        cutoff_time = current_time - self.time_window

        # Remove all timestamps older than the time window
        # popleft() removes from the left (oldest end) - it's optimized for deque
        while self.request_timestamps and self.request_timestamps[0] < cutoff_time:
            self.request_timestamps.popleft()

        # If we haven't hit the max, allow the request and record the timestamp
        if len(self.request_timestamps) < self.max_requests:
            self.request_timestamps.append(current_time)
            return True

        # Otherwise, reject the request
        return False

    def get_request_count(self):
        """Get the current number of active requests in the time window."""
        current_time = time.time()
        cutoff_time = current_time - self.time_window
        
        # Count how many requests are still active
        active_requests = sum(1 for ts in self.request_timestamps if ts >= cutoff_time)
        return active_requests

    def get_time_until_reset(self):
        """Get seconds until the oldest request expires and a slot opens up."""
        if not self.request_timestamps:
            return 0

        oldest_request_time = self.request_timestamps[0]
        time_until_reset = (oldest_request_time + self.time_window) - time.time()
        
        return max(0, time_until_reset)  # Never return negative numbers


# Test it out
limiter = RateLimiter(max_requests=5, time_window=10)

for i in range(7):
    allowed = limiter.is_allowed()
    count = limiter.get_request_count()
    status = "✓ ALLOWED" if allowed else "✗ REJECTED"
    print(f"Request {i+1}: {status} (active: {count})")

# Allow 100 requests per minute
limiter = RateLimiter(max_requests=100, time_window=60)

# Check each request
if limiter.is_allowed():
    # Process the request
    handle_request()
else:
    # Send 429 Too Many Requests response
    return error("Rate limit exceeded")

remaining = limiter.max_requests - limiter.get_request_count()
print(f"Requests remaining: {remaining}")

if not limiter.is_allowed():
    wait_time = limiter.get_time_until_reset()
    print(f"Try again in {wait_time:.1f} seconds")