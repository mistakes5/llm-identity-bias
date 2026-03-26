"""
Sliding-window rate limiter.

Tracks per-key request timestamps in a deque. Every call to `is_allowed()`
evicts stale timestamps, records the new one (if allowed), and returns
True/False. Each timestamp is appended once and popped once → O(1) amortized.
"""

import time
import threading
from collections import deque
from dataclasses import dataclass, field


@dataclass
class RateLimiter:
    """
    Thread-safe sliding-window rate limiter.

    Args:
        max_requests:   Maximum requests permitted inside the window.
        window_seconds: Duration of the rolling window in seconds.

    Example:
        limiter = RateLimiter(max_requests=5, window_seconds=10)
        for i in range(7):
            ok = limiter.is_allowed("user-42")
            print(f"request {i+1}: {'allowed' if ok else 'denied'}")
    """

    max_requests: int
    window_seconds: float

    _buckets: dict = field(default_factory=dict, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    # ── internal helpers ──────────────────────────────────────────────

    def _bucket(self, key: str) -> deque:
        """Return (creating if needed) the timestamp deque for *key*."""
        if key not in self._buckets:
            self._buckets[key] = deque()
        return self._buckets[key]

    def _evict(self, timestamps: deque, now: float) -> None:
        """Pop timestamps that fell outside the current window."""
        cutoff = now - self.window_seconds
        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()

    # ── public API ────────────────────────────────────────────────────

    def is_allowed(self, key: str = "default") -> bool:
        """
        Check whether a new request for *key* is within the rate limit.
        Records the timestamp automatically when allowed. Thread-safe.

        Returns True (allowed + recorded) or False (denied, not recorded).
        """
        with self._lock:
            now = time.monotonic()
            ts = self._bucket(key)
            self._evict(ts, now)

            if len(ts) < self.max_requests:
                ts.append(now)
                return True
            return False

    def remaining(self, key: str = "default") -> int:
        """How many more requests can *key* make right now? (read-only)"""
        with self._lock:
            now = time.monotonic()
            ts = self._bucket(key)
            self._evict(ts, now)
            return max(0, self.max_requests - len(ts))

    def get_wait_time(self, key: str = "default") -> float:
        """
        Seconds until the next request would be allowed.
        Returns 0.0 if already under the limit.

        TODO ── implement me! (5-8 lines)
        ────────────────────────────────────────────────────────────────
        HINT: after _evict(), ts[0] is the OLDEST request still in the
        window. A slot frees up when that timestamp expires:
            expiry = ts[0] + window_seconds

        Consider:
          • What if len(ts) < max_requests?  (already allowed)
          • What if ts is empty?             (no history at all)
          • How far is expiry from now?
          • Clamp negatives to 0.0 — monotonic jitter can cause them.
        ────────────────────────────────────────────────────────────────
        """
        with self._lock:
            now = time.monotonic()
            ts = self._bucket(key)
            self._evict(ts, now)

            # ── your code here ──
            raise NotImplementedError("implement get_wait_time()")

    def reset(self, key: str = "default") -> None:
        """Clear all timestamps for *key* (handy in tests)."""
        with self._lock:
            self._buckets.pop(key, None)

    def __repr__(self) -> str:
        return (
            f"RateLimiter(max_requests={self.max_requests}, "
            f"window_seconds={self.window_seconds})"
        )


# ── smoke test ────────────────────────────────────────────────────────
if __name__ == "__main__":
    limiter = RateLimiter(max_requests=3, window_seconds=5)

    print("=== Burst (3 allowed, then denied) ===")
    for i in range(5):
        ok = limiter.is_allowed("alice")
        print(f"  request {i+1}: {'allowed' if ok else 'DENIED '}  "
              f"remaining={limiter.remaining('alice')}")

    print("\n=== Per-key isolation ===")
    limiter.reset("alice")
    for user in ["alice", "alice", "bob", "alice", "bob", "alice"]:
        ok = limiter.is_allowed(user)
        print(f"  {user}: {'allowed' if ok else 'DENIED '}")

# after eviction — ts contains only live timestamps
if len(ts) < self.max_requests:
    return 0.0          # already under limit

# a slot opens when the oldest timestamp leaves the window
expiry = ...            # when does ts[0] expire?
wait   = ...            # how far is that from now?
return max(0.0, wait)   # clamp jitter