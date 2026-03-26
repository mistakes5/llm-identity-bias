from collections import deque
from typing import Optional
import time
import threading


class RateLimiter:
    """
    Allows up to `max_requests` calls within any rolling `window_seconds` window.

    Usage:
        limiter = RateLimiter(max_requests=5, window_seconds=10)
        if limiter.is_allowed():
            process_request()
        else:
            print(f"Retry in {limiter.reset_after():.2f}s")
    """

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        if max_requests < 1:
            raise ValueError("max_requests must be >= 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")

        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: deque[float] = deque()
        self._lock = threading.Lock()

    def is_allowed(self) -> bool:
        """Check if a new request is within the limit. Atomic (thread-safe)."""
        now = time.monotonic()
        with self._lock:
            self._evict(now)
            if len(self._timestamps) < self.max_requests:
                self._timestamps.append(now)
                return True
            return False

    def remaining(self) -> int:
        """How many more requests are allowed right now."""
        now = time.monotonic()
        with self._lock:
            self._evict(now)
            return max(0, self.max_requests - len(self._timestamps))

    def reset_after(self) -> float:
        """Seconds until at least one slot opens. Returns 0.0 if one is already free."""
        now = time.monotonic()
        with self._lock:
            self._evict(now)
            if len(self._timestamps) < self.max_requests:
                return 0.0
            return max(0.0, self._timestamps[0] + self.window_seconds - now)

    def wait_for_slot(self, timeout: Optional[float] = None) -> bool:
        """Block until a slot is available (or timeout). Returns True if acquired."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            wait = self.reset_after()
            if wait == 0.0:
                if self.is_allowed():
                    return True
                continue  # another thread grabbed it — retry
            if deadline is not None and time.monotonic() + wait > deadline:
                return False
            time.sleep(min(wait, 0.05))

    def _evict(self, now: float) -> None:
        """Drop timestamps outside the current window (called under lock)."""
        cutoff = now - self.window_seconds
        while self._timestamps and self._timestamps[0] <= cutoff:
            self._timestamps.popleft()

    def __repr__(self) -> str:
        return (
            f"RateLimiter(max={self.max_requests}, "
            f"window={self.window_seconds}s, "
            f"remaining={self.remaining()})"
        )


class KeyedRateLimiter:
    """Per-key limiter — one bucket per user, IP, API key, etc."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._limiters: dict[str, RateLimiter] = {}
        self._lock = threading.Lock()

    def _get(self, key: str) -> RateLimiter:
        with self._lock:
            if key not in self._limiters:
                self._limiters[key] = RateLimiter(self.max_requests, self.window_seconds)
            return self._limiters[key]

    def is_allowed(self, key: str) -> bool: return self._get(key).is_allowed()
    def remaining(self, key: str) -> int:   return self._get(key).remaining()
    def reset_after(self, key: str) -> float: return self._get(key).reset_after()

rl = RateLimiter(max_requests=3, window_seconds=5)

for i in range(5):
    ok = rl.is_allowed()
    print(f"Request {i+1}: {'✓' if ok else f'✗ retry in {rl.reset_after():.2f}s'}")

# Request 1: ✓
# Request 2: ✓
# Request 3: ✓
# Request 4: ✗ retry in 4.99s
# Request 5: ✗ retry in 4.99s