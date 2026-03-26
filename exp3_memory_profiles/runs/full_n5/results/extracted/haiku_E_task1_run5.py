import time

class RateLimiter:
    # This class helps prevent too many requests in a short time
    # Example: allow 5 requests per 10 seconds
    
    def __init__(self, max_requests, time_window):
        # max_requests: how many requests allowed (e.g., 5)
        # time_window: the time period in seconds (e.g., 10)
        self.max_requests = max_requests
        self.time_window = time_window
        self.request_times = []  # This stores when each request happened

    def is_allowed(self):
        # Returns True if request is allowed, False if blocked
        
        current_time = time.time()  # Get current time in seconds
        
        # Remove timestamps that are too old (outside our time window)
        # pop(0) removes the first (oldest) item from the list
        while self.request_times and self.request_times[0] < current_time - self.time_window:
            self.request_times.pop(0)
        
        # Check if we can make another request
        if len(self.request_times) < self.max_requests:
            self.request_times.append(current_time)  # Record this request time
            return True  # Request allowed!
        else:
            return False  # We hit the limit

    def get_requests_remaining(self):
        # Returns how many more requests you can make
        
        current_time = time.time()
        
        # Clean up old timestamps first
        while self.request_times and self.request_times[0] < current_time - self.time_window:
            self.request_times.pop(0)
        
        # Calculate: max allowed minus how many we've used
        remaining = self.max_requests - len(self.request_times)
        return remaining

    def reset(self):
        # Clear all request history to start fresh
        self.request_times = []


# Example: Test it out!
limiter = RateLimiter(max_requests=5, time_window=10)

for i in range(1, 8):
    if limiter.is_allowed():
        print(f"Request {i}: ALLOWED (remaining: {limiter.get_requests_remaining()})")
    else:
        print(f"Request {i}: BLOCKED (remaining: {limiter.get_requests_remaining()})")

# Create a limiter: 5 requests per 10 seconds
limiter = RateLimiter(max_requests=5, time_window=10)

# Before handling a request, check:
if limiter.is_allowed():
    print("Request allowed!")
else:
    print("Too many requests. Try again later.")

# Show user how many they have left:
remaining = limiter.get_requests_remaining()
print(f"You have {remaining} requests left")

# Start fresh if needed:
limiter.reset()

# Limit users to 10 new to-do items per minute
todo_limiter = RateLimiter(max_requests=10, time_window=60)

def create_todo(user_id, title, description):
    if not todo_limiter.is_allowed():
        print("Slow down! You're creating too many items.")
        return False
    
    # Add the to-do item
    print(f"Created: {title}")
    return True