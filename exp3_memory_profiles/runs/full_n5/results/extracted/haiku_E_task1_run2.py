import time
from collections import defaultdict

# A simple rate limiter that allows N requests per time window
class RateLimiter:
    """
    Rate limiter that tracks requests and enforces limits.

    Example:
        limiter = RateLimiter(max_requests=5, time_window=60)
        if limiter.is_allowed("user_123"):
            print("Request allowed!")
        else:
            print("Rate limit exceeded")
    """

    def __init__(self, max_requests, time_window):
        """
        Initialize the rate limiter.

        Args:
            max_requests: How many requests are allowed in the time window
            time_window: Size of the time window in seconds
        """
        # Store how many requests we allow
        self.max_requests = max_requests

        # Store the time window size (in seconds)
        self.time_window = time_window

        # Dictionary to store request timestamps for each user/identifier
        # Key: user identifier (like "user_123")
        # Value: list of timestamps when that user made requests
        self.requests = defaultdict(list)

    def is_allowed(self, identifier):
        """
        Check if a request from the given identifier is allowed.

        This function:
        1. Removes old requests that are outside the time window
        2. Checks if we've hit the limit
        3. Records the new request timestamp if allowed

        Args:
            identifier: A unique ID for the user/request source (e.g., "user_123", "192.168.1.1")

        Returns:
            True if the request is allowed, False if rate limit is exceeded
        """

        # Get the current time as a timestamp (seconds since 1970)
        current_time = time.time()

        # Calculate how far back our time window goes
        # For example, if time_window is 60 seconds, this is 60 seconds ago
        window_start = current_time - self.time_window

        # Get the list of request timestamps for this identifier
        request_timestamps = self.requests[identifier]

        # Remove any requests that are OLDER than our time window
        # We keep only requests that happened after window_start
        # This is like saying "forget about requests older than 60 seconds"
        self.requests[identifier] = [
            timestamp for timestamp in request_timestamps
            if timestamp > window_start
        ]

        # After cleaning up old requests, check how many recent requests we have
        recent_requests_count = len(self.requests[identifier])

        # If we've already hit the limit, deny this request
        if recent_requests_count >= self.max_requests:
            return False

        # If we haven't hit the limit, allow the request
        # Record the timestamp of THIS request
        self.requests[identifier].append(current_time)
        return True

    def get_request_count(self, identifier):
        """
        Get how many requests this identifier has made recently (within the time window).

        Args:
            identifier: A unique ID for the user/request source

        Returns:
            Number of requests in the current time window
        """
        current_time = time.time()
        window_start = current_time - self.time_window

        # Count how many requests are still within the window
        recent_requests = [
            timestamp for timestamp in self.requests[identifier]
            if timestamp > window_start
        ]

        return len(recent_requests)

    def reset(self, identifier):
        """
        Clear all request history for a specific identifier.

        Args:
            identifier: A unique ID to reset
        """
        self.requests[identifier] = []


# Example usage and testing
if __name__ == "__main__":
    # Create a rate limiter that allows 3 requests per 10 seconds
    limiter = RateLimiter(max_requests=3, time_window=10)

    print("=== Rate Limiter Demo ===\n")

    # Test with user_1
    print("Testing with 'user_1' (3 requests allowed per 10 seconds):")
    for i in range(5):
        allowed = limiter.is_allowed("user_1")
        count = limiter.get_request_count("user_1")
        status = "✓ ALLOWED" if allowed else "✗ DENIED"
        print(f"  Request {i+1}: {status} (Total in window: {count})")

    print("\n--- Waiting 5 seconds ---")
    time.sleep(5)

    # Try another request after waiting
    print("\nAfter 5 second wait:")
    allowed = limiter.is_allowed("user_1")
    count = limiter.get_request_count("user_1")
    status = "✓ ALLOWED" if allowed else "✗ DENIED"
    print(f"  Request: {status} (Total in window: {count})")

    # Test with a different user
    print("\nTesting with 'user_2' (independent limit):")
    for i in range(3):
        allowed = limiter.is_allowed("user_2")
        count = limiter.get_request_count("user_2")
        status = "✓ ALLOWED" if allowed else "✗ DENIED"
        print(f"  Request {i+1}: {status} (Total in window: {count})")

    # Show that user_2's next request is denied
    allowed = limiter.is_allowed("user_2")
    count = limiter.get_request_count("user_2")
    status = "✓ ALLOWED" if allowed else "✗ DENIED"
    print(f"  Request 4: {status} (Total in window: {count})")

# Create a limiter: 5 requests per 60 seconds
limiter = RateLimiter(max_requests=5, time_window=60)

# Check if a user can make a request
if limiter.is_allowed("user_123"):
    print("Request accepted!")
else:
    print("Rate limit exceeded - try again later")

# Check how many requests they've made
count = limiter.get_request_count("user_123")
print(f"You've made {count} requests so far")

# Reset a user's limit
limiter.reset("user_123")

limiter = RateLimiter(max_requests=10, time_window=60)  # 10 tasks per minute

def add_task(user_id, task_text):
    if not limiter.is_allowed(user_id):
        print("You're creating tasks too fast! Wait a moment.")
        return False
    
    # Add the task to database here
    print(f"Task added: {task_text}")
    return True