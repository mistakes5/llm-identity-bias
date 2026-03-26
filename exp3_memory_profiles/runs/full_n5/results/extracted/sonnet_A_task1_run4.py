"""
rate_limiter.py — Sliding window log rate limiter.

Tracks exact request timestamps per key and allows at most `limit` requests
within any rolling `window_seconds` interval.

Complexity:
  Time  — O(r) per call, where r = active requests in the window
  Space — O(k × r), where k = unique keys
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RateLimitResult:
    """
    Attributes:
        allowed      — True if the request was accepted and its timestamp recorded.
        remaining    — Requests still available in the current window.
        reset_after  — Seconds until the oldest timestamp expires (remaining +1).
        retry_after  — Only set when denied; seconds until the caller may retry.
    """
    allowed: bool
    remaining: int
    reset_after: float
    retry_after: Optional[float] = None


class RateLimiter:
    """
    Sliding window log rate limiter.

    `is_allowed(key)` checks whether `key` has issued fewer than `limit`
    requests in the most recent `window_seconds` seconds. Allowed requests
    are recorded immediately; denied requests have no side effects.

    Example:
        limiter = RateLimiter(limit=5, window_seconds=60)
        result = limiter.is_allowed("user:42")
        if not result.allowed:
            return f"Retry in {result.retry_after:.1f}s"
    """

    def __init__(self, limit: int, window_seconds: float) -> None:
        if limit <= 0:
            raise ValueError(f"limit must be positive, got {limit!r}")
        if window_seconds <= 0:
            raise ValueError(f"window_seconds must be positive, got {window_seconds!r}")

        self.limit = limit
        self.window = window_seconds
        # key → deque of monotonic timestamps, oldest at the left
        self._buckets: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def is_allowed(self, key: str) -> RateLimitResult:
        """
        Check and (if allowed) record a request for `key`.

        Args:
            key — Identifier for the rate-limited entity (user ID, IP, etc.)
        """
        now = time.monotonic()
        cutoff = now - self.window

        with self._lock:
            bucket = self._buckets[key]
            _evict(bucket, cutoff)

            count = len(bucket)
            if count < self.limit:
                bucket.append(now)
                remaining = self.limit - count - 1
                reset_after = (bucket[0] - cutoff) if bucket else self.window
                return RateLimitResult(
                    allowed=True,
                    remaining=remaining,
                    reset_after=reset_after,
                )
            else:
                retry_after = bucket[0] - cutoff   # oldest entry → next free slot
                return RateLimitResult(
                    allowed=False,
                    remaining=0,
                    reset_after=retry_after,
                    retry_after=retry_after,
                )

    def peek(self, key: str) -> dict:
        """
        Read the current state for `key` without recording a request.
        Useful for populating X-RateLimit-* response headers.
        """
        now = time.monotonic()
        cutoff = now - self.window
        with self._lock:
            bucket = self._buckets[key]
            _evict(bucket, cutoff)
            count = len(bucket)
            return {
                "count": count,
                "remaining": max(0, self.limit - count),
                "limit": self.limit,
                "window_seconds": self.window,
            }

    def reset(self, key: str) -> None:
        """Clear all recorded timestamps for `key` (admin override / testing)."""
        with self._lock:
            self._buckets.pop(key, None)

    def cleanup(self, max_idle_seconds: Optional[float] = None) -> int:
        """
        Remove entries for keys whose last request has expired.

        Without this, `_buckets` grows unboundedly as new keys appear
        (unique IPs, ephemeral session IDs, etc.). Call periodically from
        a background thread or a scheduler.

        Args:
            max_idle_seconds — Remove a key if its newest timestamp is older
                than this. Defaults to `self.window` — i.e. any key whose
                bucket would be entirely empty after eviction.

        Returns:
            Number of keys removed.

        TODO ────────────────────────────────────────────────────────────────
        Implement this method. Here's what to fill in (5–8 lines):

            cutoff = time.monotonic() - (max_idle_seconds or self.window)
            # snapshot keys so we can delete while iterating safely
            # for each key: evict its bucket, then drop it if empty or stale
            # return removed count

        Key design trade-off to consider:
          ┌─ Option A: hold self._lock for the entire loop
          │   Simple and fully consistent.
          │   Blocks is_allowed() callers during large dict scans.
          │
          └─ Option B: snapshot keys, then lock only per-deletion
              is_allowed() can proceed between deletions.
              May miss keys added between snapshot and deletion pass.

        Option A is correct for most services. Reach for Option B only
        if _buckets holds 100k+ keys and lock contention is measurable.
        ─────────────────────────────────────────────────────────────────────
        """
        raise NotImplementedError


# ------------------------------------------------------------------ #
# Internal helper                                                      #
# ------------------------------------------------------------------ #

def _evict(bucket: deque[float], cutoff: float) -> None:
    """Pop timestamps that have fallen outside the active window."""
    while bucket and bucket[0] <= cutoff:
        bucket.popleft()

def cleanup(self, max_idle_seconds: Optional[float] = None) -> int:
    # YOUR CODE HERE — 6–8 lines
    raise NotImplementedError