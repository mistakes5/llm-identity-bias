# rate_limiter.py
from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from threading import Lock
from typing import Callable


@dataclass
class _Bucket:
    """Per-key state: timestamp deque + its own lock."""
    timestamps: deque[float] = field(default_factory=deque)
    lock: Lock = field(default_factory=Lock)


@dataclass(frozen=True)
class RateCheckResult:
    allowed: bool
    remaining: int           # slots left in this window
    retry_after: float       # seconds to wait if denied; 0.0 if allowed
    requests_in_window: int  # stamped requests in the current window


class RateLimiter:
    """
    Sliding-window rate limiter with per-key tracking.

    >>> limiter = RateLimiter(max_requests=5, window_seconds=60.0)
    >>> limiter.is_allowed("user:42")
    True
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        if max_requests < 1:
            raise ValueError("max_requests must be ≥ 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._registry_lock = Lock()
        self._buckets: dict[str, _Bucket] = defaultdict(_Bucket)

    def _get_bucket(self, key: str) -> _Bucket:
        with self._registry_lock:
            return self._buckets[key]

    def _evict_expired(self, bucket: _Bucket, now: float) -> None:
        """Remove timestamps that have slid out of the window (caller holds lock)."""
        cutoff = now - self.window_seconds
        while bucket.timestamps and bucket.timestamps[0] <= cutoff:
            bucket.timestamps.popleft()

    def check(self, key: str = "global", *, record: bool = True) -> RateCheckResult:
        """
        Check (and optionally record) a request for *key*.

        Parameters
        ----------
        key    : Any identifier — user ID, IP, API token, etc.
        record : If True and allowed, stamps the timestamp. Pass False to peek.
        """
        now = time.monotonic()
        bucket = self._get_bucket(key)

        with bucket.lock:
            self._evict_expired(bucket, now)
            count = len(bucket.timestamps)
            allowed = count < self.max_requests

            if allowed and record:
                bucket.timestamps.append(now)
                count += 1

            remaining = max(0, self.max_requests - count)

            retry_after = 0.0
            if not allowed and bucket.timestamps:
                # Next slot opens when the oldest stamp slides out of the window
                retry_after = max(0.0, bucket.timestamps[0] + self.window_seconds - now)

            return RateCheckResult(
                allowed=allowed,
                remaining=remaining,
                retry_after=retry_after,
                requests_in_window=count,
            )

    def is_allowed(self, key: str = "global") -> bool:
        """Thin wrapper — True if the request is within the limit."""
        return self.check(key).allowed

    def peek(self, key: str = "global") -> RateCheckResult:
        """Read current state without consuming a slot."""
        return self.check(key, record=False)

    def reset(self, key: str) -> None:
        """Clear all timestamps for *key* (e.g. after an admin unban)."""
        bucket = self._get_bucket(key)
        with bucket.lock:
            bucket.timestamps.clear()

    def timestamps(self, key: str = "global") -> list[float]:
        """Snapshot of raw monotonic timestamps for *key*."""
        bucket = self._get_bucket(key)
        with bucket.lock:
            return list(bucket.timestamps)

    def limit(self, key_fn: Callable[..., str] | None = None):
        """
        Decorator factory — raises RateLimitExceeded when the limit is hit.

        @limiter.limit()                          # key = function's qualname
        def fetch():  ...

        @limiter.limit(key_fn=lambda uid, **_: f"user:{uid}")
        def get_profile(uid: str): ...
        """
        import functools

        def decorator(fn: Callable) -> Callable:
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                key = key_fn(*args, **kwargs) if key_fn else fn.__qualname__
                result = self.check(key)
                if not result.allowed:
                    raise RateLimitExceeded(result)
                return fn(*args, **kwargs)
            return wrapper
        return decorator

    def __repr__(self) -> str:
        return f"RateLimiter(max_requests={self.max_requests}, window_seconds={self.window_seconds})"


class RateLimitExceeded(Exception):
    def __init__(self, result: RateCheckResult) -> None:
        self.result = result
        super().__init__(f"Rate limit exceeded. Retry after {result.retry_after:.3f}s.")

# Usage examples

limiter = RateLimiter(max_requests=3, window_seconds=10.0)

# ── 1. Basic check ──
result = limiter.check("user:42")
print(result)  # RateCheckResult(allowed=True, remaining=2, retry_after=0.0, ...)

# ── 2. Boolean shorthand ──
if limiter.is_allowed("user:42"):
    print("proceed")

# ── 3. Peek (no slot consumed — useful for X-RateLimit-* headers) ──
state = limiter.peek("user:42")
print(f"{state.remaining} requests remaining")

# ── 4. Decorator pattern ──
@limiter.limit(key_fn=lambda user_id, **_: f"user:{user_id}")
def get_profile(user_id: str) -> dict:
    return {"id": user_id}

try:
    for _ in range(5):
        get_profile("alice")   # raises on the 4th call
except RateLimitExceeded as e:
    print(e)                   # "Rate limit exceeded. Retry after 9.821s."
    print(e.result.retry_after)

# ── 5. Admin reset ──
limiter.reset("user:42")

import random

def backoff_strategy(result: RateCheckResult, attempt: int = 1) -> float:
    """
    Return seconds to wait before retrying after a RateLimitExceeded.

    Parameters
    ----------
    result  : The RateCheckResult from the denied check() call.
    attempt : Which retry this is (1-indexed). Use for exponential scaling.
    """
    # ~5-8 lines — your implementation here
    raise NotImplementedError