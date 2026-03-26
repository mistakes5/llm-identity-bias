# src/rate_limiter.py
"""
Sliding Window Rate Limiter
---------------------------
Tracks request timestamps per key (e.g. user ID, IP address) and
enforces a maximum of `max_requests` within a rolling `window_seconds`
time window.

Strategy: Sliding Window Log
  - Exact accuracy — no boundary burst artifacts
  - Memory: O(max_requests) per tracked key (old timestamps are evicted)
  - Thread-safe via a per-instance lock
"""

import threading
import time
from collections import deque
from dataclasses import dataclass


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: int       # requests left in the current window
    retry_after: float   # seconds until next slot opens (0.0 if allowed)
    request_count: int   # total accepted requests for this key (lifetime)


class RateLimiter:
    def __init__(self, max_requests: int, window_seconds: float) -> None:
        if max_requests < 1:
            raise ValueError("max_requests must be >= 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")

        self.max_requests = max_requests
        self.window_seconds = window_seconds

        # deque gives O(1) append + popleft — ideal for sliding window
        self._timestamps: dict[str, deque[float]] = {}
        self._total_accepted: dict[str, int] = {}
        self._lock = threading.Lock()

    def _evict_expired(self, dq: deque[float], now: float) -> None:
        """Remove timestamps that have fallen outside the current window."""
        cutoff = now - self.window_seconds
        while dq and dq[0] <= cutoff:
            dq.popleft()

    def _get_or_create(self, key: str) -> deque[float]:
        if key not in self._timestamps:
            self._timestamps[key] = deque()
            self._total_accepted[key] = 0
        return self._timestamps[key]

    def check(self, key: str, now: float | None = None) -> RateLimitResult:
        """
        Decide whether to allow the next request for *key*.
        """
        with self._lock:
            # ── Your implementation goes here (~8 lines) ───────────────
            #
            # Steps:
            #  1. Resolve `now` — use time.time() if not provided (lets
            #     tests inject a fake clock for deterministic results).
            #  2. Get-or-create the deque: self._get_or_create(key)
            #  3. Evict expired timestamps: self._evict_expired(dq, now)
            #  4. Count in-window requests: len(dq)
            #  5. ALLOWED (count < self.max_requests):
            #       - append `now` to dq
            #       - increment self._total_accepted[key]
            #       - return RateLimitResult(allowed=True,
            #                               remaining=self.max_requests - len(dq),
            #                               retry_after=0.0,
            #                               request_count=self._total_accepted[key])
            #  6. DENIED:
            #       - retry_after = dq[0] + self.window_seconds - now
            #         (oldest timestamp tells you exactly when a slot opens)
            #       - return RateLimitResult(allowed=False, remaining=0,
            #                               retry_after=retry_after,
            #                               request_count=self._total_accepted[key])
            #
            raise NotImplementedError("Implement check() — see steps above")
            # ──────────────────────────────────────────────────────────

    # Inspection helpers (already implemented)

    def get_timestamps(self, key: str) -> list[float]:
        """Return a snapshot of in-window timestamps for *key*."""
        with self._lock:
            if key not in self._timestamps:
                return []
            dq = self._timestamps[key]
            self._evict_expired(dq, time.time())
            return list(dq)

    def reset(self, key: str) -> None:
        """Clear all state for *key*."""
        with self._lock:
            self._timestamps.pop(key, None)
            self._total_accepted.pop(key, None)

    def stats(self, key: str) -> dict:
        """Human-readable stats for *key*."""
        with self._lock:
            if key not in self._timestamps:
                return {"key": key, "in_window": 0, "total_accepted": 0}
            dq = self._timestamps[key]
            self._evict_expired(dq, time.time())
            return {
                "key": key,
                "in_window": len(dq),
                "remaining": max(0, self.max_requests - len(dq)),
                "total_accepted": self._total_accepted.get(key, 0),
            }

# test_rate_limiter.py

from rate_limiter import RateLimiter

def test_basic_allow():
    rl = RateLimiter(max_requests=3, window_seconds=10)
    for i in range(3):
        r = rl.check("user-1", now=0.0)
        assert r.allowed, f"Request {i+1} should be allowed"
    print("✓ basic_allow")

def test_deny_on_overflow():
    rl = RateLimiter(max_requests=3, window_seconds=10)
    for _ in range(3):
        rl.check("user-1", now=0.0)
    r = rl.check("user-1", now=0.0)
    assert not r.allowed
    assert r.remaining == 0
    assert r.retry_after > 0
    print("✓ deny_on_overflow")

def test_window_slides():
    rl = RateLimiter(max_requests=3, window_seconds=10)
    for _ in range(3):
        rl.check("user-1", now=0.0)
    # Advance time past the window — all old timestamps evicted
    r = rl.check("user-1", now=11.0)
    assert r.allowed, "Should allow after window expires"
    print("✓ window_slides")

def test_remaining_decrements():
    rl = RateLimiter(max_requests=5, window_seconds=60)
    for expected_remaining in [4, 3, 2, 1, 0]:
        r = rl.check("user-1", now=0.0)
        assert r.remaining == expected_remaining, \
            f"Expected {expected_remaining}, got {r.remaining}"
    print("✓ remaining_decrements")

def test_keys_are_isolated():
    rl = RateLimiter(max_requests=2, window_seconds=10)
    rl.check("alice", now=0.0)
    rl.check("alice", now=0.0)
    r_alice = rl.check("alice", now=0.0)
    r_bob   = rl.check("bob",   now=0.0)
    assert not r_alice.allowed
    assert r_bob.allowed
    print("✓ keys_are_isolated")

def test_retry_after_accuracy():
    rl = RateLimiter(max_requests=2, window_seconds=10)
    rl.check("user-1", now=0.0)   # slot used at t=0
    rl.check("user-1", now=3.0)   # slot used at t=3
    r = rl.check("user-1", now=5.0)
    assert not r.allowed
    # oldest timestamp is 0.0; window=10; retry = 0+10-5 = 5.0
    assert abs(r.retry_after - 5.0) < 0.001, f"Expected 5.0, got {r.retry_after}"
    print("✓ retry_after_accuracy")

if __name__ == "__main__":
    test_basic_allow()
    test_deny_on_overflow()
    test_window_slides()
    test_remaining_decrements()
    test_keys_are_isolated()
    test_retry_after_accuracy()
    print("\nAll tests passed ✓")