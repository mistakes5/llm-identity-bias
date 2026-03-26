"""
rate_limiter.py — sliding window log + token bucket

Sliding window: exact, O(N) memory per key (N = limit).
Token bucket:   O(1) memory, tolerates short bursts.
"""

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int       # slots/tokens left right now
    retry_after: float   # seconds until next slot opens (0 if allowed)
    limit: int
    window_seconds: float


# ─── Sliding Window Log ────────────────────────────────────────────────────

@dataclass
class _WindowState:
    timestamps: deque = field(default_factory=deque)
    lock: threading.Lock = field(default_factory=threading.Lock)


class SlidingWindowRateLimiter:
    """
    Exact sliding-window rate limiter.

    Keeps a per-key deque of accepted timestamps; evicts expired entries
    on every call.  No approximation error.  O(N) memory per key.

    Thread-safe: fine-grained per-key locks.
    """

    def __init__(self, limit: int, window_seconds: float) -> None:
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("limit and window_seconds must be > 0")
        self.limit = limit
        self.window_seconds = window_seconds
        self._states: dict[str, _WindowState] = defaultdict(_WindowState)
        self._map_lock = threading.Lock()

    def check(self, key: str = "default", *, now: Optional[float] = None) -> RateLimitResult:
        """Check and record a request. Mutates state if allowed."""
        ts = now if now is not None else time.monotonic()
        cutoff = ts - self.window_seconds
        state = self._state_for(key)

        with state.lock:
            self._evict(state, cutoff)

            active = len(state.timestamps)
            allowed = active < self.limit
            if allowed:
                state.timestamps.append(ts)
                active += 1

            retry_after = 0.0
            if not allowed and state.timestamps:
                retry_after = (state.timestamps[0] + self.window_seconds) - ts

            return RateLimitResult(
                allowed=allowed,
                remaining=max(0, self.limit - active),
                retry_after=retry_after,
                limit=self.limit,
                window_seconds=self.window_seconds,
            )

    def peek(self, key: str = "default", *, now: Optional[float] = None) -> RateLimitResult:
        """Read-only check — does NOT record a timestamp."""
        ts = now if now is not None else time.monotonic()
        cutoff = ts - self.window_seconds
        state = self._state_for(key)

        with state.lock:
            self._evict(state, cutoff)
            active = len(state.timestamps)
            retry_after = 0.0
            if active >= self.limit and state.timestamps:
                retry_after = (state.timestamps[0] + self.window_seconds) - ts
            return RateLimitResult(
                allowed=active < self.limit,
                remaining=max(0, self.limit - active),
                retry_after=retry_after,
                limit=self.limit,
                window_seconds=self.window_seconds,
            )

    def timestamps(self, key: str = "default", *, now: Optional[float] = None) -> list[float]:
        """Snapshot of all active request timestamps for a key."""
        ts = now if now is not None else time.monotonic()
        state = self._state_for(key)
        with state.lock:
            self._evict(state, ts - self.window_seconds)
            return list(state.timestamps)

    def reset(self, key: str) -> None:
        state = self._state_for(key)
        with state.lock:
            state.timestamps.clear()

    def _state_for(self, key: str) -> _WindowState:
        with self._map_lock:
            return self._states[key]

    @staticmethod
    def _evict(state: _WindowState, cutoff: float) -> None:
        while state.timestamps and state.timestamps[0] <= cutoff:
            state.timestamps.popleft()


# ─── Token Bucket ──────────────────────────────────────────────────────────

@dataclass
class _BucketState:
    tokens: float
    last_refill: float
    lock: threading.Lock = field(default_factory=threading.Lock)


class TokenBucketRateLimiter:
    """
    Token bucket rate limiter.

    Tokens accumulate at `rate` tokens/second, capped at `capacity`.
    Each accepted request consumes one token.  Bursts up to `capacity`
    are allowed as long as the bucket is full.  O(1) memory per key.

    Args:
        capacity:  Max tokens (= max burst size).
        rate:      Replenishment speed in tokens/second.
    """

    def __init__(self, capacity: float, rate: float) -> None:
        if capacity <= 0 or rate <= 0:
            raise ValueError("capacity and rate must be > 0")
        self.capacity = capacity
        self.rate = rate
        self.window_seconds = capacity / rate   # steady-state window equivalent
        self._states: dict[str, _BucketState] = {}
        self._map_lock = threading.Lock()

    def check(self, key: str = "default", *, now: Optional[float] = None) -> RateLimitResult:
        ts = now if now is not None else time.monotonic()
        state = self._state_for(key, ts)

        with state.lock:
            self._refill(state, ts)
            allowed = state.tokens >= 1.0
            if allowed:
                state.tokens -= 1.0
            remaining = max(0, int(state.tokens))
            retry_after = 0.0 if allowed else (1.0 - state.tokens) / self.rate
            return RateLimitResult(
                allowed=allowed,
                remaining=remaining,
                retry_after=retry_after,
                limit=int(self.capacity),
                window_seconds=self.window_seconds,
            )

    def peek(self, key: str = "default", *, now: Optional[float] = None) -> RateLimitResult:
        ts = now if now is not None else time.monotonic()
        state = self._state_for(key, ts)
        with state.lock:
            self._refill(state, ts)
            remaining = max(0, int(state.tokens))
            allowed = state.tokens >= 1.0
            retry_after = 0.0 if allowed else (1.0 - state.tokens) / self.rate
            return RateLimitResult(
                allowed=allowed,
                remaining=remaining,
                retry_after=retry_after,
                limit=int(self.capacity),
                window_seconds=self.window_seconds,
            )

    def _refill(self, state: _BucketState, now: float) -> None:
        """
        Lazy refill — add tokens proportional to elapsed time.
        Called inside state.lock.

        TODO: implement this (5-7 lines)
        """
        raise NotImplementedError

    def _state_for(self, key: str, now: float) -> _BucketState:
        with self._map_lock:
            if key not in self._states:
                self._states[key] = _BucketState(tokens=self.capacity, last_refill=now)
            return self._states[key]

def _refill(self, state: _BucketState, now: float) -> None:
    # Your implementation here (~5-7 lines)
    ...