"""
Rate limiter implementation supporting N requests per time window.

Features:
- Sliding window rate limiting
- Automatic cleanup of old timestamps (prevents memory leaks)
- Thread-safe operations
- Per-identifier tracking (user, IP, API key, etc.)
"""

import time
from collections import defaultdict, deque
from threading import Lock
from typing import Dict, Deque, Tuple


class RateLimiter:
    """
    Rate limiter that tracks requests and enforces rate limits.

    Uses a sliding window approach where requests are tracked with timestamps.
    Old timestamps are automatically cleaned up to prevent memory leaks.

    Args:
        max_requests: Maximum number of requests allowed per time window
        window_seconds: Time window duration in seconds
        cleanup_interval: How many checks before triggering cleanup (performance optimization)
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        cleanup_interval: int = 100
    ):
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        if cleanup_interval <= 0:
            raise ValueError("cleanup_interval must be positive")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.cleanup_interval = cleanup_interval

        # Store deques of timestamps for each identifier
        self._requests: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()
        self._check_count = 0

    def is_allowed(self, identifier: str) -> bool:
        """
        Check if a request is allowed for the given identifier.

        Args:
            identifier: Unique identifier (user ID, IP address, API key, etc.)

        Returns:
            True if request is allowed, False if rate limit exceeded
        """
        with self._lock:
            current_time = time.time()
            requests = self._requests[identifier]

            # Remove timestamps outside the current window
            cutoff_time = current_time - self.window_seconds
            while requests and requests[0] < cutoff_time:
                requests.popleft()

            # Check if request is allowed
            allowed = len(requests) < self.max_requests

            # Add current timestamp if allowed
            if allowed:
                requests.append(current_time)

            # Periodically clean up old identifiers with no recent activity
            self._check_count += 1
            if self._check_count >= self.cleanup_interval:
                self._cleanup_idle_identifiers(cutoff_time)
                self._check_count = 0

            return allowed

    def _cleanup_idle_identifiers(self, cutoff_time: float) -> None:
        """Remove identifiers that have no requests in the current window."""
        to_remove = [
            identifier
            for identifier, requests in self._requests.items()
            if not requests or (requests and requests[-1] < cutoff_time)
        ]
        for identifier in to_remove:
            del self._requests[identifier]

    def get_request_count(self, identifier: str) -> int:
        """Get the current number of requests for an identifier within the window."""
        with self._lock:
            current_time = time.time()
            requests = self._requests[identifier]

            # Clean old timestamps
            cutoff_time = current_time - self.window_seconds
            while requests and requests[0] < cutoff_time:
                requests.popleft()

            return len(requests)

    def get_reset_time(self, identifier: str) -> Tuple[float, float]:
        """
        Get the time remaining until the next request is allowed.

        Returns:
            Tuple of (seconds_until_available, timestamp_of_reset)
        """
        with self._lock:
            current_time = time.time()
            requests = self._requests[identifier]

            if not requests:
                return (0.0, current_time)

            # Time when the oldest request will leave the window
            oldest_request = requests[0]
            reset_time = oldest_request + self.window_seconds
            seconds_until_available = max(0.0, reset_time - current_time)

            return (seconds_until_available, reset_time)

    def reset(self, identifier: str = None) -> None:
        """
        Reset rate limit for a specific identifier or all identifiers.

        Args:
            identifier: If None, resets all identifiers
        """
        with self._lock:
            if identifier is None:
                self._requests.clear()
            else:
                self._requests[identifier].clear()


class AdaptiveRateLimiter(RateLimiter):
    """
    Rate limiter with adaptive limits based on burst detection.

    Allows brief bursts but enforces average rate over time.
    Useful for APIs that need to handle legitimate traffic spikes.
    """

    def __init__(
        self,
        max_requests: int,
        window_seconds: float,
        burst_multiplier: float = 1.5,
        cleanup_interval: int = 100
    ):
        """
        Args:
            burst_multiplier: Allow up to this multiple of max_requests in a burst.
                             Must be >= 1.0
        """
        if burst_multiplier < 1.0:
            raise ValueError("burst_multiplier must be >= 1.0")

        super().__init__(max_requests, window_seconds, cleanup_interval)
        self.burst_multiplier = burst_multiplier
        self.burst_limit = int(max_requests * burst_multiplier)

    def is_allowed(self, identifier: str) -> bool:
        """Allow requests up to burst limit, but enforce average rate."""
        with self._lock:
            current_time = time.time()
            requests = self._requests[identifier]

            # Remove old timestamps
            cutoff_time = current_time - self.window_seconds
            while requests and requests[0] < cutoff_time:
                requests.popleft()

            # Allow if under burst limit
            allowed = len(requests) < self.burst_limit

            if allowed:
                requests.append(current_time)

            # Cleanup
            self._check_count += 1
            if self._check_count >= self.cleanup_interval:
                self._cleanup_idle_identifiers(cutoff_time)
                self._check_count = 0

            return allowed

# Basic: 5 requests per 10 seconds per user
limiter = RateLimiter(max_requests=5, window_seconds=10)

if limiter.is_allowed("user_123"):
    # Process request
    pass
else:
    wait_time, reset_at = limiter.get_reset_time("user_123")
    print(f"Rate limited. Retry in {wait_time:.1f}s")

# Adaptive: Allow bursts but enforce 3 req/sec average
adaptive = AdaptiveRateLimiter(max_requests=3, window_seconds=1, burst_multiplier=2.0)
if adaptive.is_allowed("api_client_456"):
    process_request()