import time
from collections import deque  # deque = "double-ended queue", like a list but faster at removing from the front


class RateLimiter:
    """
    A rate limiter that allows up to max_requests within a rolling time window.

    Example:
        limiter = RateLimiter(max_requests=5, window_seconds=10)
        if limiter.is_allowed():
            print("Request approved!")
        else:
            print("Too many requests. Slow down!")
    """

    def __init__(self, max_requests, window_seconds):
        # How many requests we allow in the time window
        self.max_requests = max_requests

        # How long the time window is, in seconds (e.g. 10 = last 10 seconds)
        self.window_seconds = window_seconds

        # A deque (list-like) that stores the timestamp of each past request
        # time.time() gives us a float like 1711234567.42 (seconds since 1970)
        self.timestamps = deque()

    # -------------------------------------------------------------------------
    # Private helper: removes timestamps that are too old to matter anymore
    # Methods starting with _ are a convention meaning "internal use only"
    # -------------------------------------------------------------------------
    def _clean_old_requests(self):
        current_time = time.time()

        # Keep removing the OLDEST timestamp (front of deque) if it's
        # outside our window. Stop as soon as we find one that's recent enough.
        while self.timestamps and self.timestamps[0] < current_time - self.window_seconds:
            self.timestamps.popleft()  # popleft() removes from the front

    # -------------------------------------------------------------------------
    # TODO: Your turn! Implement the core logic below.
    # -------------------------------------------------------------------------
    def is_allowed(self):
        """
        Check if a new request should be allowed right now.
        Returns True if allowed, False if the limit is exceeded.
        """
        pass  # ← replace this with your code!

    # -------------------------------------------------------------------------
    # Bonus helpers (already written for you)
    # -------------------------------------------------------------------------
    def get_request_count(self):
        """Returns how many requests have been made in the current window."""
        self._clean_old_requests()
        return len(self.timestamps)

    def time_until_next_allowed(self):
        """Returns how many seconds until the next request would be allowed."""
        self._clean_old_requests()
        if len(self.timestamps) < self.max_requests:
            return 0
        oldest_timestamp = self.timestamps[0]
        wait_time = (oldest_timestamp + self.window_seconds) - time.time()
        return max(0, wait_time)


# =============================================================================
# Quick test — run this file directly:  python rate_limiter.py
# =============================================================================
if __name__ == "__main__":
    # Allow 3 requests every 5 seconds
    limiter = RateLimiter(max_requests=3, window_seconds=5)

    print("Sending 5 requests...\n")
    for i in range(1, 6):
        allowed = limiter.is_allowed()
        count = limiter.get_request_count()
        wait = limiter.time_until_next_allowed()

        status = "✓ ALLOWED" if allowed else "✗ BLOCKED"
        print(f"Request {i}: {status}  |  Active requests: {count}  |  Wait: {wait:.2f}s")