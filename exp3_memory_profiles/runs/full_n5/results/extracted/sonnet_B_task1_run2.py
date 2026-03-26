"""
rate_limiter.py — Sliding window log rate limiter

Allows at most `max_requests` per `window_seconds` per key.
Thread-safe. Timestamps stored in a deque for O(1) amortised eviction.
"""

from __future__ import annotations
import time
from collections import deque
from dataclasses import dataclass
from threading import Lock


@dataclass
class RateLimitResult:
    """All metadata needed to build HTTP 429 / Retry-After headers."""
    allowed: bool
    remaining: int     # slots left in the current window
    reset_in: float    # seconds until oldest recorded request expires
    retry_after: float # seconds to wait before retrying; 0.0 when allowed

    def __str__(self) -> str:
        status = "✓ allowed" if self.allowed else "✗ denied "
        return (f"{status} | remaining={self.remaining} | "
                f"reset_in={self.reset_in:.2f}s | retry_after={self.retry_after:.2f}s")


class RateLimiter:
    """
    Sliding window log rate limiter.

    Maintains a deque of monotonic timestamps per key. On each check(),
    expired entries are lazily evicted from the left, then the live count
    is compared to max_requests.

    Thread safety: each key owns its own (deque, Lock) pair; the top-level
    dict is guarded by a separate lock so concurrent key creation is safe.
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        if max_requests <= 0:
            raise ValueError(f"max_requests must be > 0, got {max_requests}")
        if window_seconds <= 0:
            raise ValueError(f"window_seconds must be > 0, got {window_seconds}")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, tuple[deque[float], Lock]] = {}
        self._buckets_lock = Lock()

    # ── Public API ────────────────────────────────────────────────────────

    def check(self, key: str = "default") -> RateLimitResult:
        """
        Admit (and record) a request. Returns RateLimitResult.

        Sequence — all inside the per-key lock:
          1. Evict timestamps older than (now - window_seconds)
          2. Admit if count < max_requests, otherwise deny
          3. Return result with remaining / reset_in / retry_after
        """
        timestamps, lock = self._get_bucket(key)
        now = time.monotonic()
        cutoff = now - self.window_seconds

        with lock:
            # 1. Lazy eviction — O(k) where k = number of expired entries
            while timestamps and timestamps[0] < cutoff:
                timestamps.popleft()

            # 2. Admission
            if len(timestamps) < self.max_requests:
                timestamps.append(now)
                allowed = True
            else:
                allowed = False

            # 3. Metadata
            remaining   = max(0, self.max_requests - len(timestamps))
            reset_in    = max(0.0, timestamps[0] + self.window_seconds - now) if timestamps else 0.0
            retry_after = reset_in if not allowed else 0.0

            return RateLimitResult(allowed, remaining, reset_in, retry_after)

    def peek(self, key: str = "default") -> RateLimitResult:
        """Read-only status check — does NOT record a request."""
        timestamps, lock = self._get_bucket(key)
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with lock:
            while timestamps and timestamps[0] < cutoff:
                timestamps.popleft()
            count     = len(timestamps)
            allowed   = count < self.max_requests
            remaining = max(0, self.max_requests - count)
            reset_in  = max(0.0, timestamps[0] + self.window_seconds - now) if timestamps else 0.0
            return RateLimitResult(allowed, remaining, reset_in,
                                   reset_in if not allowed else 0.0)

    def reset(self, key: str = "default") -> None:
        """Clear all recorded timestamps for key (e.g. after penalty expiry)."""
        timestamps, lock = self._get_bucket(key)
        with lock:
            timestamps.clear()

    def snapshot(self, key: str = "default") -> list[float]:
        """Live timestamp copy for debugging or serialisation."""
        timestamps, lock = self._get_bucket(key)
        now = time.monotonic()
        cutoff = now - self.window_seconds
        with lock:
            while timestamps and timestamps[0] < cutoff:
                timestamps.popleft()
            return list(timestamps)

    # ── Internals ─────────────────────────────────────────────────────────

    def _get_bucket(self, key: str) -> tuple[deque[float], Lock]:
        with self._buckets_lock:
            if key not in self._buckets:
                self._buckets[key] = (deque(), Lock())
            return self._buckets[key]

    def __repr__(self) -> str:
        return (f"RateLimiter(max_requests={self.max_requests}, "
                f"window_seconds={self.window_seconds}, "
                f"active_keys={len(self._buckets)})")

limiter = RateLimiter(max_requests=10, window_seconds=60)

result = limiter.check("user:42")   # records the request
if not result.allowed:
    raise Exception(f"Rate limited. Retry in {result.retry_after:.1f}s")

limiter.peek("user:42")   # read-only — does not consume a slot
limiter.reset("user:42")  # clear on auth upgrade / penalty expiry
limiter.snapshot("user:42")  # list of raw timestamps for debugging