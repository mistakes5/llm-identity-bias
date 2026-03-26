"""
Rate limiter implementations: sliding window log, token bucket, fixed window.
All strategies are thread-safe and memory-leak-free.
"""

from __future__ import annotations

import threading
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field


# ── Base ──────────────────────────────────────────────────────────────────────

@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int       # tokens left in current window
    retry_after: float   # seconds until next slot opens (0 if allowed)
    reset_at: float      # wall-clock epoch when window/bucket fully resets


class RateLimiter(ABC):
    @abstractmethod
    def is_allowed(self, key: str = "default") -> RateLimitResult:
        """Check and consume one token for `key`."""

    @abstractmethod
    def peek(self, key: str = "default") -> RateLimitResult:
        """Inspect state without consuming a token."""

    @abstractmethod
    def reset(self, key: str = "default") -> None:
        """Clear all state for `key`."""


# ── Sliding Window Log ────────────────────────────────────────────────────────

class SlidingWindowRateLimiter(RateLimiter):
    """
    Exact sliding window via per-key timestamp deque.
    Space: O(N) per key. Expired entries evicted on every call — no leak.
    """

    def __init__(self, limit: int, window_seconds: float) -> None:
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("limit and window_seconds must be positive")
        self.limit = limit
        self.window = window_seconds
        self._locks: dict[str, threading.Lock] = {}
        self._logs: dict[str, deque[float]] = {}
        self._meta = threading.Lock()

    def _state(self, key: str) -> tuple[threading.Lock, deque[float]]:
        with self._meta:
            if key not in self._logs:
                self._locks[key] = threading.Lock()
                self._logs[key] = deque()
            return self._locks[key], self._logs[key]

    def _evict(self, log: deque[float], now: float) -> None:
        cutoff = now - self.window
        while log and log[0] <= cutoff:
            log.popleft()

    def is_allowed(self, key: str = "default") -> RateLimitResult:
        lock, log = self._state(key)
        now = time.monotonic()
        with lock:
            self._evict(log, now)
            if len(log) < self.limit:
                log.append(now)
                return RateLimitResult(
                    allowed=True,
                    remaining=self.limit - len(log),
                    retry_after=0.0,
                    reset_at=time.time() + self.window,
                )
            retry_after = (log[0] + self.window) - now
            return RateLimitResult(
                allowed=False, remaining=0,
                retry_after=max(retry_after, 0.0),
                reset_at=time.time() + retry_after,
            )

    def peek(self, key: str = "default") -> RateLimitResult:
        lock, log = self._state(key)
        now = time.monotonic()
        with lock:
            self._evict(log, now)
            if len(log) < self.limit:
                return RateLimitResult(
                    allowed=True, remaining=self.limit - len(log),
                    retry_after=0.0, reset_at=time.time() + self.window,
                )
            retry_after = (log[0] + self.window) - now
            return RateLimitResult(
                allowed=False, remaining=0,
                retry_after=max(retry_after, 0.0),
                reset_at=time.time() + retry_after,
            )

    def reset(self, key: str = "default") -> None:
        lock, log = self._state(key)
        with lock:
            log.clear()

    def timestamps(self, key: str = "default") -> list[float]:
        """Snapshot of active monotonic timestamps. Useful for testing/inspection."""
        lock, log = self._state(key)
        now = time.monotonic()
        with lock:
            self._evict(log, now)
            return list(log)


# ── Token Bucket ──────────────────────────────────────────────────────────────

@dataclass
class _Bucket:
    tokens: float
    last_refill: float = field(default_factory=time.monotonic)
    lock: threading.Lock = field(default_factory=threading.Lock)


class TokenBucketRateLimiter(RateLimiter):
    """
    Token bucket with continuous refill. Handles burst up to `limit` tokens.
    Refill rate: limit / window_seconds tokens per second.
    """

    def __init__(self, limit: int, window_seconds: float) -> None:
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("limit and window_seconds must be positive")
        self.limit = limit
        self.window = window_seconds
        self.rate = limit / window_seconds  # tokens/sec
        self._buckets: dict[str, _Bucket] = {}
        self._meta = threading.Lock()

    def _get(self, key: str) -> _Bucket:
        with self._meta:
            if key not in self._buckets:
                self._buckets[key] = _Bucket(tokens=float(self.limit))
            return self._buckets[key]

    def _refill(self, b: _Bucket, now: float) -> None:
        b.tokens = min(self.limit, b.tokens + (now - b.last_refill) * self.rate)
        b.last_refill = now

    def is_allowed(self, key: str = "default") -> RateLimitResult:
        b = self._get(key)
        now = time.monotonic()
        with b.lock:
            self._refill(b, now)
            if b.tokens >= 1.0:
                b.tokens -= 1.0
                return RateLimitResult(
                    allowed=True, remaining=int(b.tokens),
                    retry_after=0.0,
                    reset_at=time.time() + (self.limit - b.tokens) / self.rate,
                )
            retry_after = (1.0 - b.tokens) / self.rate
            return RateLimitResult(
                allowed=False, remaining=0,
                retry_after=retry_after,
                reset_at=time.time() + self.limit / self.rate,
            )

    def peek(self, key: str = "default") -> RateLimitResult:
        b = self._get(key)
        now = time.monotonic()
        with b.lock:
            self._refill(b, now)
            t = b.tokens
        if t >= 1.0:
            return RateLimitResult(
                allowed=True, remaining=int(t), retry_after=0.0,
                reset_at=time.time() + (self.limit - t) / self.rate,
            )
        return RateLimitResult(
            allowed=False, remaining=0,
            retry_after=(1.0 - t) / self.rate,
            reset_at=time.time() + self.limit / self.rate,
        )

    def reset(self, key: str = "default") -> None:
        b = self._get(key)
        with b.lock:
            b.tokens = float(self.limit)
            b.last_refill = time.monotonic()


# ── Fixed Window ──────────────────────────────────────────────────────────────

@dataclass
class _Window:
    count: int = 0
    start: float = field(default_factory=time.monotonic)
    lock: threading.Lock = field(default_factory=threading.Lock)


class FixedWindowRateLimiter(RateLimiter):
    """
    Fixed window counter. O(1) space. Caveat: allows up to 2×N at window boundaries.
    Use SlidingWindow or TokenBucket for strict guarantees.
    """

    def __init__(self, limit: int, window_seconds: float) -> None:
        if limit <= 0 or window_seconds <= 0:
            raise ValueError("limit and window_seconds must be positive")
        self.limit = limit
        self.window = window_seconds
        self._windows: dict[str, _Window] = {}
        self._meta = threading.Lock()

    def _get(self, key: str) -> _Window:
        with self._meta:
            if key not in self._windows:
                self._windows[key] = _Window()
            return self._windows[key]

    def _roll(self, w: _Window, now: float) -> None:
        if now - w.start >= self.window:
            w.count = 0
            w.start = now

    def is_allowed(self, key: str = "default") -> RateLimitResult:
        w = self._get(key)
        now = time.monotonic()
        with w.lock:
            self._roll(w, now)
            reset_in = self.window - (now - w.start)
            if w.count < self.limit:
                w.count += 1
                return RateLimitResult(
                    allowed=True, remaining=self.limit - w.count,
                    retry_after=0.0, reset_at=time.time() + reset_in,
                )
            return RateLimitResult(
                allowed=False, remaining=0,
                retry_after=reset_in, reset_at=time.time() + reset_in,
            )

    def peek(self, key: str = "default") -> RateLimitResult:
        w = self._get(key)
        now = time.monotonic()
        with w.lock:
            self._roll(w, now)
            reset_in = self.window - (now - w.start)
            allowed = w.count < self.limit
            return RateLimitResult(
                allowed=allowed,
                remaining=max(self.limit - w.count, 0),
                retry_after=0.0 if allowed else reset_in,
                reset_at=time.time() + reset_in,
            )

    def reset(self, key: str = "default") -> None:
        w = self._get(key)
        with w.lock:
            w.count = 0
            w.start = time.monotonic()

rl = SlidingWindowRateLimiter(limit=10, window_seconds=60)

result = rl.is_allowed(key="user:42")
if not result.allowed:
    raise TooManyRequests(f"retry in {result.retry_after:.2f}s")

# Non-destructive check (doesn't consume a token)
status = rl.peek(key="user:42")

# Inspect raw timestamps (sliding window only)
ts = rl.timestamps(key="user:42")