"""
Sliding window log rate limiter.

Algorithm: exact sliding window — tracks request timestamps in a deque,
evicts on every check. Memory is bounded at O(max_requests) per key.

Thread-safe via per-instance Lock. For distributed use, swap the deque +
Lock for a Redis sorted set + MULTI/EXEC (ZADD/ZREMRANGEBYSCORE/ZCARD).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from typing import Callable


@dataclass
class RateLimitState:
    """Snapshot returned by every check() call."""
    allowed: bool
    remaining: int
    reset_after: float   # seconds until a slot opens; 0.0 if under limit
    window_size: float
    max_requests: int


class RateLimiter:
    """
    Sliding window log rate limiter — exact, timestamp-aware.

    Single key:
        rl = RateLimiter(max_requests=10, window_seconds=60)
        state = rl.check()

    Per-client (e.g. by IP):
        state = rl.check(key=request.client_ip)
        if not state.allowed:
            raise TooManyRequests(retry_after=state.reset_after)
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        if max_requests < 1:
            raise ValueError("max_requests must be >= 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._windows: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def check(self, key: str = "__default__") -> RateLimitState:
        """
        Check whether a new request is allowed for `key`.
        Records the timestamp if allowed. Never raises.
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            ts = self._windows[key]
            self._evict(ts, cutoff)

            allowed = len(ts) < self.max_requests
            if allowed:
                ts.append(now)

            remaining = max(0, self.max_requests - len(ts))
            reset_after = (
                ts[0] + self.window_seconds - now
                if ts and not allowed
                else 0.0
            )

        return RateLimitState(
            allowed=allowed,
            remaining=remaining,
            reset_after=round(reset_after, 4),
            window_size=self.window_seconds,
            max_requests=self.max_requests,
        )

    def timestamps(self, key: str = "__default__") -> list[float]:
        """Snapshot of active (non-expired) request timestamps for `key`."""
        cutoff = time.monotonic() - self.window_seconds
        with self._lock:
            ts = self._windows[key]
            self._evict(ts, cutoff)
            return list(ts)

    def reset(self, key: str = "__default__") -> None:
        with self._lock:
            self._windows[key].clear()

    def reset_all(self) -> None:
        with self._lock:
            self._windows.clear()

    # ------------------------------------------------------------------
    # Decorator interface — YOUR CONTRIBUTION
    # ------------------------------------------------------------------

    def limit(self, key_fn: Callable[..., str] | None = None) -> Callable:
        """
        Decorator that gates calls through the rate limiter.

            @rl.limit(key_fn=lambda req: req.client_ip)
            def handle(req): ...

        TODO: implement the body below (~8-12 lines).
        """
        def decorator(fn: Callable) -> Callable:
            # YOUR IMPLEMENTATION HERE
            raise NotImplementedError
        return decorator

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _evict(ts: deque[float], cutoff: float) -> None:
        while ts and ts[0] <= cutoff:
            ts.popleft()

    def __repr__(self) -> str:
        return f"RateLimiter(max_requests={self.max_requests}, window_seconds={self.window_seconds})"

def decorator(fn: Callable) -> Callable:
    # YOUR IMPLEMENTATION HERE (~8-12 lines)
    raise NotImplementedError