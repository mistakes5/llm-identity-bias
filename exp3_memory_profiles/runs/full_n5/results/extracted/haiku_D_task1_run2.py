class FixedWindowCounter(RateLimiter):
    """Divides time into fixed buckets."""
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.lock = threading.Lock()
        self.request_count = 0
        self.window_start = time.time()

    def is_allowed(self) -> bool:
        with self.lock:
            now = time.time()
            if now - self.window_start >= self.window_seconds:
                self.window_start = now
                self.request_count = 0
            if self.request_count < self.max_requests:
                self.request_count += 1
                return True
            return False

class SlidingWindowLog(RateLimiter):
    """Tracks actual request timestamps in a deque."""
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.lock = threading.Lock()
        self.request_times: deque = deque()

    def is_allowed(self) -> bool:
        with self.lock:
            now = time.time()
            # Purge expired timestamps
            while self.request_times and self.request_times[0] <= now - self.window_seconds:
                self.request_times.popleft()
            
            if len(self.request_times) < self.max_requests:
                self.request_times.append(now)
                return True
            return False

class TokenBucket(RateLimiter):
    """Tokens accumulate; each request consumes one."""
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_tokens = max_requests
        self.refill_rate = max_requests / window_seconds
        self.lock = threading.Lock()
        self.tokens = max_requests
        self.last_refill = time.time()

    def is_allowed(self) -> bool:
        with self.lock:
            now = time.time()
            elapsed = now - self.last_refill
            
            # Refill tokens based on time elapsed
            self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now
            
            if self.tokens >= 1:
                self.tokens -= 1
                return True
            return False

class SlidingWindowCounter(RateLimiter):
    """Two-window hybrid: accurate, low memory."""
    def __init__(self, max_requests: int, window_seconds: float):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.lock = threading.Lock()
        self.current_count = 0
        self.previous_count = 0
        self.window_start = time.time()

    def is_allowed(self) -> bool:
        with self.lock:
            now = time.time()
            time_passed = now - self.window_start
            
            # Shift window if expired
            if time_passed >= self.window_seconds:
                self.previous_count = self.current_count
                self.current_count = 0
                self.window_start = now
                time_passed = 0
            
            # Weighted average: requests from previous window decay linearly
            weight = 1 - (time_passed / self.window_seconds)
            estimated = self.current_count + self.previous_count * weight
            
            if estimated < self.max_requests:
                self.current_count += 1
                return True
            return False

limiter = SlidingWindowCounter(max_requests=100, window_seconds=60)

# Check if request is allowed
if limiter.is_allowed():
    process_request()
else:
    raise RateLimitExceeded("Quota exceeded, retry in 60s")