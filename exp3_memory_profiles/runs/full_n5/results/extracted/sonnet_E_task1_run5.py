# rate_limiter.py
# A sliding-window rate limiter: allows up to N requests per time window.

import time  # The built-in 'time' module lets us get the current time


class RateLimiter:
    """
    Tracks request timestamps and decides whether a new request is allowed.

    Example:
        limiter = RateLimiter(max_requests=5, window_seconds=60)
        if limiter.is_allowed():
            print("Request approved!")
        else:
            print("Too many requests. Slow down!")
    """

    def __init__(self, max_requests, window_seconds):
        # max_requests   -- how many requests are allowed per window (e.g. 5)
        # window_seconds -- how long the window is in seconds (e.g. 60 = 1 minute)
        self.max_requests = max_requests
        self.window_seconds = window_seconds

        # A list to store the timestamp of each approved request.
        # Timestamps are floats like 1711234567.891 (seconds since 1970).
        self.timestamps = []

    # ------------------------------------------------------------------ #
    # Private helper — the underscore means "internal use only"           #
    # ------------------------------------------------------------------ #

    def _remove_old_timestamps(self):
        """Delete timestamps that have fallen outside the current window."""
        current_time = time.time()

        # Anything older than this cutoff is outside the window
        cutoff_time = current_time - self.window_seconds

        # List comprehension: keep only timestamps newer than the cutoff.
        # Reads as: "give me t, for each t in self.timestamps, if t > cutoff_time"
        self.timestamps = [t for t in self.timestamps if t > cutoff_time]

    # ------------------------------------------------------------------ #
    # YOUR TURN — implement is_allowed() below!                           #
    # ------------------------------------------------------------------ #

    def is_allowed(self):
        """
        Decide whether a new request is permitted right now.

        Returns True  if the request is within the limit (and records it).
        Returns False if the limit has been reached.

        Steps to implement (about 5-6 lines):
          1. Call self._remove_old_timestamps()       <-- always clean up first
          2. Check: len(self.timestamps) < self.max_requests
          3. If True:
               - Add the current time: self.timestamps.append(time.time())
               - Return True
          4. If False:
               - Return False
        """
        # TODO: write your implementation here!
        pass

    # ------------------------------------------------------------------ #
    # Bonus utilities — already done for you                              #
    # ------------------------------------------------------------------ #

    def get_request_count(self):
        """Return how many requests have been made in the current window."""
        self._remove_old_timestamps()
        return len(self.timestamps)  # len() counts items in a list

    def seconds_until_next_allowed(self):
        """Return how many seconds until the next request slot opens up."""
        self._remove_old_timestamps()

        # If we haven't hit the limit, no waiting needed
        if len(self.timestamps) < self.max_requests:
            return 0

        # The oldest timestamp is at index 0 (we always append to the end).
        # Once it's older than window_seconds, a slot frees up.
        oldest_timestamp = self.timestamps[0]
        wait_time = oldest_timestamp + self.window_seconds - time.time()
        return round(wait_time, 2)  # round() makes it look cleaner

    def reset(self):
        """Clear all timestamps — useful for testing."""
        self.timestamps = []  # just replace with a fresh empty list


# ====================================================================== #
# Quick demo — runs when you execute this file directly                   #
# ====================================================================== #

if __name__ == "__main__":
    # Create a limiter: 3 requests allowed every 10 seconds
    limiter = RateLimiter(max_requests=3, window_seconds=10)

    print("Sending 5 requests...")
    for i in range(1, 6):
        result = limiter.is_allowed()   # will be None until you implement it!
        count = limiter.get_request_count()
        wait = limiter.seconds_until_next_allowed()
        print(f"  Request {i}: allowed={result}  |  used={count}/{limiter.max_requests}  |  wait={wait}s")

def is_allowed(self):
    # Step 1: clean up expired timestamps first
    self._remove_old_timestamps()

    # Step 2: check if we're under the limit
    if len(self.timestamps) < self.max_requests:
        # Step 3a: we're allowed — record this moment and say yes
        self.timestamps.append(time.time())
        return True

    # Step 3b: limit reached — say no
    return False