"""
rate_limiter.py

Sliding-window rate limiter — allows N requests per rolling time window.

Algorithm overview
------------------
For each key (user ID, IP, etc.) we maintain a deque of monotonic timestamps.
On every call:
  1. Evict timestamps that have aged out of the current window.
  2. Admit if the remaining count is below max_requests.
  3. Record the new timestamp only if admitted.

Time  complexity : O(k) per call, k = requests inside the window.
Space complexity : O(N × K), N = max_requests, K = distinct keys.
"""

from __future__ import annotations

import time
import threading
from collections import deque
from dataclasses import dataclass, field


@dataclass
class _Bucket:
    """Per-key state. Each bucket has its own lock — different keys never contend."""
    timestamps: deque[float] = field(default_factory=deque)
    lock: threading.Lock = field(default_factory=threading.Lock)


class RateLimiter:
    """
    Thread-safe sliding-window rate limiter.

    Parameters
    ----------
    max_requests   : int   — requests allowed per window
    window_seconds : float — rolling window duration in seconds

    Example
    -------
    limiter = RateLimiter(max_requests=5, window_seconds=60.0)
    if limiter.is_allowed("user-42"):
        handle_request()
    else:
        return 429
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        if max_requests < 1:
            raise ValueError(f"max_requests must be >= 1, got {max_requests}")
        if window_seconds <= 0:
            raise ValueError(f"window_seconds must be > 0, got {window_seconds}")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, _Bucket] = {}
        self._registry_lock = threading.Lock()

    # ── Public API ──────────────────────────────────────────────────────

    def is_allowed(self, key: str) -> bool:
        """
        Check if a new request from key is within the rate limit.
        Admitted → records timestamp, returns True.
        Denied   → state unchanged, returns False.
        """
        bucket = self._get_or_create_bucket(key)
        now = time.monotonic()

        with bucket.lock:
            self._evict_expired(bucket, now)
            if len(bucket.timestamps) < self.max_requests:
                bucket.timestamps.append(now)
                return True
            return False

    def get_usage(self, key: str) -> dict:
        """
        Snapshot usage for key without consuming a request slot.

        Returns dict with:
          used             — requests in the current window
          remaining        — slots still available
          window_resets_in — seconds until oldest request expires (0.0 if empty)
        """
        bucket = self._get_or_create_bucket(key)
        now = time.monotonic()

        with bucket.lock:
            self._evict_expired(bucket, now)
            used = len(bucket.timestamps)
            resets_in = (
                (bucket.timestamps[0] + self.window_seconds - now)
                if bucket.timestamps else 0.0
            )

        return {
            "used": used,
            "remaining": max(0, self.max_requests - used),
            "window_resets_in": round(max(0.0, resets_in), 4),
        }

    def reset(self, key: str) -> None:
        """Clear all timestamps for key (e.g. after re-auth or manual unblock)."""
        bucket = self._get_or_create_bucket(key)
        with bucket.lock:
            bucket.timestamps.clear()

    def tracked_keys(self) -> list[str]:
        """Return a snapshot of all keys currently being tracked."""
        with self._registry_lock:
            return list(self._buckets.keys())

    # ── Internal helpers ────────────────────────────────────────────────

    def _get_or_create_bucket(self, key: str) -> _Bucket:
        """Double-checked locking: fast read path, slow write path for new keys."""
        bucket = self._buckets.get(key)
        if bucket is not None:
            return bucket
        with self._registry_lock:
            if key not in self._buckets:
                self._buckets[key] = _Bucket()
            return self._buckets[key]

    def _evict_expired(self, bucket: _Bucket, now: float) -> None:
        """
        Remove timestamps that have aged out of the current window.
        Called while bucket.lock is already held — do NOT re-acquire it.

        The deque is ordered oldest → newest (left → right).
        Once the front timestamp is still valid, all others must be too.

        TODO ─────────────────────────────────────────────────────────
        Implement here (3–5 lines).

        Hints
        -----
        • boundary = now - self.window_seconds
        • Timestamps <= boundary are expired (outside the window).
        • bucket.timestamps.popleft() removes the oldest in O(1).
        • Stop as soon as the front is still within the window.

        Boundary edge case: if a request lands at exactly t == boundary,
        should it count as inside or outside? Strict exclusion (< boundary)
        is slightly more generous to the user; inclusive (<=) is safer for
        stricter enforcement. Pick one and stick to it.
        ──────────────────────────────────────────────────────────────
        """
        pass  # ← your implementation goes here


# ── Demo ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== RateLimiter demo: 5 req / 2s window ===\n")
    limiter = RateLimiter(max_requests=5, window_seconds=2.0)
    key = "demo-user"

    for i in range(1, 8):
        allowed = limiter.is_allowed(key)
        u = limiter.get_usage(key)
        print(f"  #{i}: {'allowed' if allowed else 'DENIED '} | "
              f"used={u['used']}/5  remaining={u['remaining']}  "
              f"resets_in={u['window_resets_in']:.3f}s")

    print("\n  Sleeping 2.1s ...")
    time.sleep(2.1)

    print("\n  After window reset:")
    for i in range(1, 4):
        allowed = limiter.is_allowed(key)
        u = limiter.get_usage(key)
        print(f"  #{i}: {'allowed' if allowed else 'DENIED '} | used={u['used']}/5")

    limiter.reset(key)
    print(f"\n  After reset: {limiter.get_usage(key)}")