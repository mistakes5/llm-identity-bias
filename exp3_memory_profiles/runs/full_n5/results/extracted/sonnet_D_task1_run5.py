"""
Rate limiter — sliding window log (exact) + sliding window counter (approximate).

Sliding window log:     O(N) memory, exact accuracy, timestamps preserved.
Sliding window counter: O(1) memory, ~worst-case 2x burst at boundary.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass, field


@dataclass(frozen=True)
class RateCheckResult:
    allowed: bool
    remaining: int
    retry_after: float  # seconds until a slot opens; 0.0 if allowed


# ─── Sliding Window Log (exact) ───────────────────────────────────────────────

class SlidingWindowLog:
    """
    Exact rate limiter. Stores every request timestamp in a deque per key.
    Evicts expired entries on each access — no background cleanup needed.
    Per-key locks minimize contention under concurrency.
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        if max_requests <= 0:
            raise ValueError(f"max_requests must be > 0, got {max_requests}")
        if window_seconds <= 0:
            raise ValueError(f"window_seconds must be > 0, got {window_seconds}")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._meta_lock = threading.Lock()

    def _get_lock(self, key: str) -> threading.Lock:
        with self._meta_lock:
            if key not in self._locks:
                self._locks[key] = threading.Lock()
                self._buckets[key] = deque()
            return self._locks[key]

    def _evict(self, timestamps: deque[float], now: float) -> None:
        cutoff = now - self.window_seconds
        while timestamps and timestamps[0] <= cutoff:
            timestamps.popleft()

    def _build_result(self, timestamps: deque[float], now: float) -> RateCheckResult:
        remaining = self.max_requests - len(timestamps)
        if remaining > 0:
            return RateCheckResult(allowed=True, remaining=remaining, retry_after=0.0)
        retry_after = round((timestamps[0] + self.window_seconds) - now, 4)
        return RateCheckResult(allowed=False, remaining=0, retry_after=retry_after)

    def consume(self, key: str) -> RateCheckResult:
        """Check and record atomically."""
        lock = self._get_lock(key)
        with lock:
            now = time.monotonic()
            ts = self._buckets[key]
            self._evict(ts, now)
            if len(ts) < self.max_requests:
                ts.append(now)
            return self._build_result(ts, now)

    def peek(self, key: str) -> RateCheckResult:
        """Check without recording — dry-run / pre-flight."""
        lock = self._get_lock(key)
        with lock:
            now = time.monotonic()
            ts = self._buckets[key]
            self._evict(ts, now)
            return self._build_result(ts, now)

    def reset(self, key: str) -> None:
        lock = self._get_lock(key)
        with lock:
            self._buckets[key].clear()

    def timestamps(self, key: str) -> list[float]:
        """Snapshot of active request timestamps for this key."""
        lock = self._get_lock(key)
        with lock:
            now = time.monotonic()
            self._evict(self._buckets[key], now)
            return list(self._buckets[key])


# ─── Sliding Window Counter (approximate) — YOUR TURN ─────────────────────────

class SlidingWindowCounter:
    """
    O(1) approximation using two fixed-size buckets.

    Estimated count = prev_count * (1 - elapsed/window) + curr_count

    Can overcount by at most max_requests at a window boundary — acceptable
    for most use cases and far cheaper than the log approach at scale.
    """

    @dataclass
    class _State:
        prev_count: int = 0
        curr_count: int = 0
        window_start: float = field(default_factory=time.monotonic)

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._state: dict[str, SlidingWindowCounter._State] = {}
        self._locks: dict[str, threading.Lock] = {}
        self._meta_lock = threading.Lock()

    def _get(self, key: str) -> tuple[SlidingWindowCounter._State, threading.Lock]:
        with self._meta_lock:
            if key not in self._state:
                self._state[key] = self._State()
                self._locks[key] = threading.Lock()
            return self._state[key], self._locks[key]

    def consume(self, key: str) -> RateCheckResult:
        # TODO: implement here (5-10 lines)
        raise NotImplementedError

    def peek(self, key: str) -> RateCheckResult:
        raise NotImplementedError

    def reset(self, key: str) -> None:
        state, lock = self._get(key)
        with lock:
            state.prev_count = 0
            state.curr_count = 0
            state.window_start = time.monotonic()

def consume(self, key: str) -> RateCheckResult:
    state, lock = self._get(key)
    with lock:
        now = time.monotonic()
        elapsed_windows = (now - state.window_start) / self.window_seconds

        # 1. Advance the window if needed:
        #    - elapsed ≥ 2: full reset (both counts → 0, window_start = now)
        #    - elapsed ≥ 1: rotate (prev = curr, curr = 0, window_start += window)
        # 2. Compute estimated = prev_count * (1 - frac) + curr_count
        #    where frac = (now - state.window_start) / self.window_seconds
        # 3. If estimated < max_requests → increment curr_count, return allowed
        # 4. Otherwise → compute retry_after, return denied