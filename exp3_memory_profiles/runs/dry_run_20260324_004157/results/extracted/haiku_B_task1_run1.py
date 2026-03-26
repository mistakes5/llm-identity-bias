import time
from collections import deque
from threading import Lock

class SlidingWindowRateLimiter:
    """Tracks actual request timestamps in a rolling window."""
    
    def __init__(self, max_requests: int, window_size_seconds: int):
        self.max_requests = max_requests
        self.window_size = window_size_seconds
        self.requests = deque()  # Timestamps of requests
        self.lock = Lock()
    
    def is_allowed(self) -> bool:
        """Check if request is allowed, add timestamp if yes."""
        with self.lock:
            now = time.time()
            cutoff = now - self.window_size
            
            # Remove timestamps outside the window
            while self.requests and self.requests[0] < cutoff:
                self.requests.popleft()
            
            # Allow if under limit
            if len(self.requests) < self.max_requests:
                self.requests.append(now)
                return True
            return False
    
    def get_reset_time(self) -> float:
        """When the oldest request leaves the window."""
        with self.lock:
            if not self.requests:
                return time.time() + self.window_size
            return self.requests[0] + self.window_size

class FixedWindowRateLimiter:
    """Resets at fixed time boundaries."""
    
    def __init__(self, max_requests: int, window_size_seconds: int):
        self.max_requests = max_requests
        self.window_size = window_size_seconds
        self.request_count = 0
        self.window_start = time.time()
        self.lock = Lock()
    
    def is_allowed(self) -> bool:
        with self.lock:
            now = time.time()
            
            # New window?
            if now - self.window_start >= self.window_size:
                self.window_start = now
                self.request_count = 0
            
            if self.request_count < self.max_requests:
                self.request_count += 1
                return True
            return False
    
    def get_reset_time(self) -> float:
        with self.lock:
            return self.window_start + self.window_size

class TokenBucketRateLimiter:
    """Refills tokens at constant rate, allows bursting."""
    
    def __init__(self, capacity: int, refill_rate_per_second: float):
        self.capacity = capacity
        self.refill_rate = refill_rate_per_second
        self.tokens = float(capacity)
        self.last_refill = time.time()
        self.lock = Lock()
    
    def is_allowed(self) -> bool:
        with self.lock:
            now = time.time()
            elapsed = now - self.last_refill
            
            # Add refilled tokens
            self.tokens = min(
                self.capacity,
                self.tokens + elapsed * self.refill_rate
            )
            self.last_refill = now
            
            # Consume 1 token
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False
    
    def get_reset_time(self) -> float:
        with self.lock:
            if self.tokens >= 1:
                return time.time()
            tokens_needed = 1 - self.tokens
            return time.time() + (tokens_needed / self.refill_rate)

class SimpleRateLimiter:
    """Use this for most cases."""
    
    def __init__(self, max_requests: int, window_seconds: int = 60):
        self._limiter = SlidingWindowRateLimiter(max_requests, window_seconds)
    
    def is_allowed(self) -> bool:
        return self._limiter.is_allowed()
    
    def get_retry_after(self) -> int:
        """Seconds until rate limit resets."""
        reset_time = self._limiter.get_reset_time()
        return max(0, int(reset_time - time.time()))

# 10 requests per 60 seconds
limiter = SimpleRateLimiter(max_requests=10, window_seconds=60)

if limiter.is_allowed():
    process_request()
else:
    return 429, f"Rate limited. Retry after {limiter.get_retry_after()}s"

from flask import request, jsonify

user_limiters = {}  # Per-user rate limiters

@app.route('/api/data')
def get_data():
    user_id = request.user.id
    
    if user_id not in user_limiters:
        user_limiters[user_id] = SimpleRateLimiter(100, 3600)  # 100/hour
    
    if not user_limiters[user_id].is_allowed():
        return jsonify({
            'error': 'Rate limited',
            'retry_after': user_limiters[user_id].get_retry_after()
        }), 429
    
    return jsonify({'data': get_user_data(user_id)})

# Refill 2 tokens per second, max 10 (can burst 10, then refill)
limiter = TokenBucketRateLimiter(capacity=10, refill_rate_per_second=2.0)

for request in incoming_requests:
    if limiter.is_allowed():
        process(request)
    else:
        queue_for_later(request)