# rate_limiter.py
from __future__ import annotations

import time
import threading
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RateLimiter:
    """
    Sliding-window rate limiter.

    Tracks the last `max_requests` timestamps per key and allows a
    request only when fewer than `max_requests` have occurred within
    the past `window_seconds`.

    Thread-safe via a per-instance reentrant lock.

    Args:
        max_requests:   Maximum number of requests allowed per window.
        window_seconds: Duration of the sliding window (seconds).
    """

    max_requests: int
    window_seconds: float
    _store: dict[str, deque[float]] = field(default_factory=dict, init=False, repr=False)
    _lock: threading.RLock = field(default_factory=threading.RLock, init=False, repr=False)

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def is_allowed(self, key: str = "default") -> bool:
        """
        Check whether a new request for *key* is within the rate limit.

        Calling this method **consumes** the slot if allowed — i.e. it
        both checks and records the request atomically.

        Returns:
            True  — request is permitted (timestamp recorded).
            False — rate limit exceeded; request should be rejected.
        """
        now = self._now()

        with self._lock:
            timestamps = self._get_window(key, now)

            if len(timestamps) < self.max_requests:
                timestamps.append(now)
                return True

            return False

    def remaining(self, key: str = "default") -> int:
        """Return the number of requests still available in the current window."""
        now = self._now()
        with self._lock:
            timestamps = self._get_window(key, now)
            return max(0, self.max_requests - len(timestamps))

    def retry_after(self, key: str = "default") -> Optional[float]:
        """
        Seconds until the next slot opens, or None if a slot is already open.

        Useful for populating a Retry-After response header.
        """
        now = self._now()
        with self._lock:
            timestamps = self._get_window(key, now)

            if len(timestamps) < self.max_requests:
                return None  # slot available right now

            # The oldest timestamp in the window will expire first.
            oldest = timestamps[0]
            return max(0.0, (oldest + self.window_seconds) - now)

    def reset(self, key: str = "default") -> None:
        """Clear all recorded timestamps for *key*."""
        with self._lock:
            self._store.pop(key, None)

    def stats(self, key: str = "default") -> dict:
        """Return a snapshot of the limiter state for *key*."""
        now = self._now()
        with self._lock:
            timestamps = self._get_window(key, now)
            used = len(timestamps)
            return {
                "key": key,
                "used": used,
                "remaining": max(0, self.max_requests - used),
                "limit": self.max_requests,
                "window_seconds": self.window_seconds,
                "retry_after": self.retry_after(key),
                "timestamps": list(timestamps),
            }

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _get_window(self, key: str, now: float) -> deque[float]:
        """
        Retrieve (or create) the timestamp deque for *key*, pruning
        entries that have fallen outside the current window.
        """
        if key not in self._store:
            # maxlen acts as a hard cap — no unbounded growth under traffic spikes.
            self._store[key] = deque(maxlen=self.max_requests)

        dq = self._store[key]
        cutoff = now - self.window_seconds

        # Evict expired timestamps from the left (oldest first).
        while dq and dq[0] <= cutoff:
            dq.popleft()

        return dq

    @staticmethod
    def _now() -> float:
        return time.monotonic()

# test_rate_limiter.py
import pytest
from rate_limiter import RateLimiter


class TestRateLimiter:

    def test_allows_requests_within_limit(self):
        rl = RateLimiter(max_requests=3, window_seconds=1.0)
        assert all(rl.is_allowed("user") for _ in range(3))

    def test_blocks_when_limit_exceeded(self):
        rl = RateLimiter(max_requests=3, window_seconds=1.0)
        for _ in range(3):
            rl.is_allowed("user")
        assert rl.is_allowed("user") is False

    def test_window_slides(self):
        rl = RateLimiter(max_requests=3, window_seconds=0.3)
        for _ in range(3):
            rl.is_allowed("user")
        assert rl.is_allowed("user") is False

        time.sleep(0.35)  # oldest timestamp has now expired

        assert rl.is_allowed("user") is True

    def test_keys_are_isolated(self):
        rl = RateLimiter(max_requests=2, window_seconds=1.0)
        for _ in range(2):
            rl.is_allowed("alice")
        # alice is exhausted — bob should still be unaffected
        assert rl.is_allowed("bob") is True

    def test_remaining_decrements(self):
        rl = RateLimiter(max_requests=5, window_seconds=1.0)
        assert rl.remaining("user") == 5
        rl.is_allowed("user")
        assert rl.remaining("user") == 4

    def test_retry_after_none_when_available(self):
        rl = RateLimiter(max_requests=3, window_seconds=1.0)
        assert rl.retry_after("user") is None

    def test_retry_after_positive_when_exhausted(self):
        rl = RateLimiter(max_requests=2, window_seconds=1.0)
        rl.is_allowed("user")
        rl.is_allowed("user")
        wait = rl.retry_after("user")
        assert wait is not None and 0 < wait <= 1.0

    def test_reset_clears_state(self):
        rl = RateLimiter(max_requests=2, window_seconds=1.0)
        rl.is_allowed("user")
        rl.is_allowed("user")
        assert rl.is_allowed("user") is False
        rl.reset("user")
        assert rl.is_allowed("user") is True

    def test_thread_safety(self):
        rl = RateLimiter(max_requests=100, window_seconds=5.0)
        results = []

        def hit():
            results.append(rl.is_allowed("shared"))

        threads = [threading.Thread(target=hit) for _ in range(200)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        allowed = sum(results)
        assert allowed == 100, f"Expected exactly 100 allowed, got {allowed}"

def _prune_expired(self, dq: deque[float], now: float) -> None:
    """
    TODO: Evict timestamps older than self.window_seconds from `dq`.
    
    Consider: should this be called by read-only methods (remaining, 
    retry_after) too, or only by is_allowed? A stale remaining() 
    might over-count available slots, which is safer for the client 
    but slightly inaccurate. Pruning everywhere is precise but does 
    more work on read-heavy workloads.
    """
    ...