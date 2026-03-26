from collections import deque
from time import time
from typing import Dict, Optional


class FixedWindowRateLimiter:
    """
    Simple fixed-window rate limiter.
    
    Memory: O(1) per client
    Accuracy: Good, except boundary spike
    
    How it works: Divide time into fixed N-second intervals. Count requests per interval.
    """
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.clients: Dict[str, tuple[int, float]] = {}

    def is_allowed(self, client_id: str) -> bool:
        now = time()
        
        if client_id not in self.clients:
            self.clients[client_id] = (1, now)
            return True

        count, window_start = self.clients[client_id]
        if now - window_start >= self.window_seconds:
            # Window reset
            self.clients[client_id] = (1, now)
            return True

        if count < self.max_requests:
            self.clients[client_id] = (count + 1, window_start)
            return True
        
        return False

class SlidingWindowLogRateLimiter:
    """
    True sliding window using timestamps.
    
    Memory: O(N) per client where N = requests in window
    Accuracy: Perfect ✓
    
    How it works: Keep exact timestamp of every request, trim old ones outside window.
    """
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.clients: Dict[str, deque] = {}

    def is_allowed(self, client_id: str) -> bool:
        now = time()
        
        if client_id not in self.clients:
            self.clients[client_id] = deque([now])
            return True

        # Evict old timestamps outside the window
        requests = self.clients[client_id]
        while requests and requests[0] <= now - self.window_seconds:
            requests.popleft()

        if len(requests) < self.max_requests:
            requests.append(now)
            return True
        
        return False

    def get_retry_after(self, client_id: str) -> Optional[float]:
        """Tell client when they can retry."""
        if client_id not in self.clients or not self.clients[client_id]:
            return None
        
        oldest = self.clients[client_id][0]
        return max(0, oldest + self.window_seconds - time())

class SlidingWindowCounterRateLimiter:
    """
    Hybrid sliding window (two fixed windows).
    
    Memory: O(1) per client
    Accuracy: ~99% (good enough for production)
    
    How it works: Track current window count + previous window count.
    Total allowed = current_count + (previous_count * overlap_ratio)
    """
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.clients: Dict[str, dict] = {}

    def is_allowed(self, client_id: str) -> bool:
        now = time()
        
        if client_id not in self.clients:
            self.clients[client_id] = {
                'current_count': 1,
                'previous_count': 0,
                'window_start': now
            }
            return True

        client = self.clients[client_id]
        time_passed = now - client['window_start']

        if time_passed >= self.window_seconds:
            # Rotate windows
            client['previous_count'] = client['current_count']
            client['current_count'] = 1
            client['window_start'] = now
            return True

        # Calculate how much of the *previous* window overlaps with our sliding window
        overlap_ratio = (self.window_seconds - time_passed) / self.window_seconds
        weighted_previous = client['previous_count'] * overlap_ratio
        total_allowed = client['current_count'] + weighted_previous

        if total_allowed < self.max_requests:
            client['current_count'] += 1
            return True
        
        return False

class TokenBucketRateLimiter:
    """
    Token bucket for burst-friendly rate limiting.
    
    Memory: O(1) per client
    Flexibility: Allows controlled bursts ✓
    
    Example: capacity=50, refill_rate=10/sec
    - Can burst 50 requests immediately
    - Then sustained at 10 req/sec (1 per 100ms)
    """
    
    def __init__(self, capacity: int, refill_rate: float):
        """
        Args:
            capacity: Bucket size (max burst requests)
            refill_rate: Tokens per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.clients: Dict[str, dict] = {}

    def is_allowed(self, client_id: str, tokens_needed: int = 1) -> bool:
        now = time()
        
        if client_id not in self.clients:
            self.clients[client_id] = {
                'tokens': self.capacity,
                'last_refill': now
            }

        client = self.clients[client_id]
        
        # Add tokens based on elapsed time
        time_since_refill = now - client['last_refill']
        tokens_to_add = time_since_refill * self.refill_rate
        client['tokens'] = min(self.capacity, client['tokens'] + tokens_to_add)
        client['last_refill'] = now

        if client['tokens'] >= tokens_needed:
            client['tokens'] -= tokens_needed
            return True
        
        return False

    def get_retry_after(self, client_id: str, tokens_needed: int = 1) -> float:
        """Tell client when they can retry."""
        if client_id not in self.clients:
            return 0.0

        client = self.clients[client_id]
        now = time()
        time_since_refill = now - client['last_refill']
        tokens_available = min(self.capacity, client['tokens'] + time_since_refill * self.refill_rate)

        if tokens_available >= tokens_needed:
            return 0.0

        deficit = tokens_needed - tokens_available
        return deficit / self.refill_rate

# Fixed window: Simple but has boundary spike
limiter = FixedWindowRateLimiter(max_requests=10, window_seconds=60)
if limiter.is_allowed("user_123"):
    process_request()
else:
    return 429  # Too Many Requests


# Sliding window log: Perfect accuracy, O(N) memory
limiter = SlidingWindowLogRateLimiter(max_requests=10, window_seconds=60)
if not limiter.is_allowed("user_456"):
    wait_time = limiter.get_retry_after("user_456")
    return {"error": f"Rate limited. Retry after {wait_time:.1f}s"}


# Sliding window counter: Production-grade (O(1) memory, 99% accurate)
limiter = SlidingWindowCounterRateLimiter(max_requests=10, window_seconds=60)
if not limiter.is_allowed("user_789"):
    return 429


# Token bucket: Burst-friendly
limiter = TokenBucketRateLimiter(capacity=50, refill_rate=10)  # 10 req/sec with 50-request burst
for i in range(100):
    if limiter.is_allowed("user_000"):
        process_request()
    else:
        wait = limiter.get_retry_after("user_000")
        print(f"Rate limited. Retry in {wait:.2f}s")