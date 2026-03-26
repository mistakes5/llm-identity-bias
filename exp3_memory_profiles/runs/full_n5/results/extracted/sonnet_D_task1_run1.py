# rate_limiter.py — Thread-safe rate limiting primitives
from __future__ import annotations

import time
import threading
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Optional


class RateLimiter(ABC):
    @abstractmethod
    def allow(self, key: str = "default") -> bool: ...
    @abstractmethod
    def remaining(self, key: str = "default") -> int: ...
    @abstractmethod
    def reset_at(self, key: str = "default") -> Optional[float]: ...


@dataclass
class SlidingWindowRateLimiter(RateLimiter):
    """Exact counts. No boundary-burst problem. O(max_requests) memory/key."""
    max_requests: int
    window_seconds: float
    _store: dict[str, deque[float]] = field(default_factory=dict, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def _evict(self, q: deque[float], cutoff: float) -> None:
        while q and q[0] <= cutoff:
            q.popleft()

    def allow(self, key: str = "default") -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._store.setdefault(key, deque())
            self._evict(q, now - self.window_seconds)
            if len(q) < self.max_requests:
                q.append(now)
                return True
            return False

    def remaining(self, key: str = "default") -> int:
        now = time.monotonic()
        with self._lock:
            if key not in self._store:
                return self.max_requests
            q = self._store[key]
            self._evict(q, now - self.window_seconds)
            return max(0, self.max_requests - len(q))

    def reset_at(self, key: str = "default") -> Optional[float]:
        with self._lock:
            q = self._store.get(key)
            if not q:
                return None
            # Convert monotonic → wall-clock epoch
            return q[0] + self.window_seconds + (time.time() - time.monotonic())

    def timestamps(self, key: str = "default") -> list[float]:
        """Snapshot of active monotonic timestamps for inspection/testing."""
        with self._lock:
            return list(self._store.get(key, []))


class TokenBucketRateLimiter(RateLimiter):
    """
    Smooth throughput with burst headroom.
    Tokens accumulate at `rate` /s up to `capacity`.
    Best for ETL pipelines rate-limiting calls to external APIs.
    """
    def __init__(self, capacity: int, rate: float) -> None:
        if capacity <= 0 or rate <= 0:
            raise ValueError("capacity and rate must be positive")
        self.capacity = capacity
        self.rate = rate
        self._buckets: dict[str, tuple[float, float]] = {}  # key → (tokens, last_mono)
        self._lock = threading.Lock()

    def _refill(self, tokens: float, last: float, now: float) -> float:
        # TODO: implement — see below
        pass

    def allow(self, key: str = "default") -> bool:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._buckets.get(key, (float(self.capacity), now))
            tokens = self._refill(tokens, last, now)
            if tokens >= 1.0:
                self._buckets[key] = (tokens - 1.0, now)
                return True
            self._buckets[key] = (tokens, now)
            return False

    def remaining(self, key: str = "default") -> int:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._buckets.get(key, (float(self.capacity), now))
            return int(self._refill(tokens, last, now))

    def reset_at(self, key: str = "default") -> Optional[float]:
        now = time.monotonic()
        with self._lock:
            tokens, last = self._buckets.get(key, (float(self.capacity), now))
            current = self._refill(tokens, last, now)
            if current >= 1.0:
                return None
            return now + (1.0 - current) / self.rate + (time.time() - time.monotonic())

def _refill(self, tokens: float, last: float, now: float) -> float:
    """
    Parameters:
        tokens  — current token count
        last    — time.monotonic() of last refill
        now     — time.monotonic() now

    Constraints to satisfy:
      1. Tokens increase by  self.rate * (now - last)
      2. Result is hard-clamped to self.capacity  ← don't leak above the ceiling
      3. Result is floor-clamped to 0.0           ← defensive against clock skew
    """
    # your implementation here