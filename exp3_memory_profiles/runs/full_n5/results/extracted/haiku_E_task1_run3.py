# Simple Rate Limiter - tracks requests over time

import time

# This dictionary will store request times for each user/request source
# Key: user identifier, Value: list of timestamps when requests happened
request_times = {}


def is_request_allowed(user_id, max_requests, time_window):
    """
    Check if a user is allowed to make a request.

    Args:
        user_id: identifier for who is making the request (like a username or IP address)
        max_requests: how many requests are allowed (like 5)
        time_window: how long the window is in seconds (like 60 for 5 requests per minute)

    Returns:
        True if the request is allowed, False if they've exceeded the limit
    """

    # Get the current time right now
    current_time = time.time()

    # If we haven't seen this user before, create an empty list for them
    if user_id not in request_times:
        request_times[user_id] = []

    # Get all the timestamps for this user
    user_timestamps = request_times[user_id]

    # Remove old timestamps that are outside the time window
    # We only care about requests in the last 'time_window' seconds
    cutoff_time = current_time - time_window
    user_timestamps[:] = [timestamp for timestamp in user_timestamps
                          if timestamp > cutoff_time]

    # Check if they've made too many requests in the time window
    if len(user_timestamps) < max_requests:
        # They're allowed! Record this new request timestamp
        user_timestamps.append(current_time)
        return True
    else:
        # They've hit the limit
        return False


class RateLimiter:
    """A rate limiter that tracks requests per user over a time window."""

    def __init__(self, max_requests, time_window):
        # Store the settings when we create the limiter
        self.max_requests = max_requests
        self.time_window = time_window
        # Dictionary to track request times
        self.request_times = {}

    def is_allowed(self, user_id):
        """Check if a request from user_id is allowed."""
        current_time = time.time()

        # Initialize user's timestamp list if needed
        if user_id not in self.request_times:
            self.request_times[user_id] = []

        timestamps = self.request_times[user_id]

        # Remove timestamps outside the window
        cutoff = current_time - self.time_window
        timestamps[:] = [t for t in timestamps if t > cutoff]

        # Check if under limit
        if len(timestamps) < self.max_requests:
            timestamps.append(current_time)
            return True
        return False

# Create a rate limiter: 5 requests per 60 seconds
api_limiter = RateLimiter(max_requests=5, time_window=60)

if api_limiter.is_allowed("user_123"):
    print("Request allowed!")
else:
    print("Rate limit exceeded")