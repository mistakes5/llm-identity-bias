import time  # lets us get the current time in seconds


# ---------------------------------------------------------------------------
# create_rate_limiter
# ---------------------------------------------------------------------------
# Instead of using a class, we store the rate limiter's state in a plain
# dictionary.  This makes it easy to inspect and understand — it's just data.
#
# Arguments:
#   max_requests   - how many requests are allowed in the time window
#   window_seconds - how long the window is (e.g. 60 = "60 seconds")
#
# Returns a dictionary with three keys:
#   "max_requests"   - the limit you passed in
#   "window_seconds" - the window size you passed in
#   "timestamps"     - a list that will grow as requests come in
# ---------------------------------------------------------------------------
def create_rate_limiter(max_requests, window_seconds):
    limiter = {
        "max_requests": max_requests,
        "window_seconds": window_seconds,
        "timestamps": [],  # starts empty; we add to this over time
    }
    return limiter


# ---------------------------------------------------------------------------
# remove_old_timestamps
# ---------------------------------------------------------------------------
# Before we can decide if a new request is allowed, we need to throw away
# timestamps that are outside the current window.  If the window is 60s and
# the current time is 1000s, any timestamp below 940s is "expired".
#
# This keeps the list from growing forever and makes our check accurate.
# ---------------------------------------------------------------------------
def remove_old_timestamps(limiter):
    now = time.time()                          # current time as a float (seconds since 1970)
    cutoff = now - limiter["window_seconds"]   # anything older than this is expired

    # Keep only timestamps that are NEWER than the cutoff.
    # List comprehension: builds a new list by looping and filtering.
    limiter["timestamps"] = [t for t in limiter["timestamps"] if t > cutoff]


# ---------------------------------------------------------------------------
# is_request_allowed
# ---------------------------------------------------------------------------
# This is the heart of the rate limiter.
#
# TODO: Your turn!  Fill in the body of this function below.
#
# Steps to implement:
#   1. Call remove_old_timestamps(limiter) to clean up expired entries first.
#   2. Count how many timestamps are currently in limiter["timestamps"].
#      Hint: use len()
#   3. Compare that count to limiter["max_requests"].
#   4. Return True if the count is *less than* the max (request is allowed).
#      Return False if the count has already hit the max (request is denied).
# ---------------------------------------------------------------------------
def is_request_allowed(limiter):
    # ✏️  Write your code here (aim for 3-5 lines):
    pass  # remove this line once you've written your code


# ---------------------------------------------------------------------------
# record_request
# ---------------------------------------------------------------------------
# Call this AFTER is_request_allowed() returns True to "use up" one slot.
# It appends the current time to the timestamps list.
# ---------------------------------------------------------------------------
def record_request(limiter):
    now = time.time()
    limiter["timestamps"].append(now)  # add current time to the list


# ---------------------------------------------------------------------------
# get_status
# ---------------------------------------------------------------------------
# A helper to see what's happening inside the limiter.
# ---------------------------------------------------------------------------
def get_status(limiter):
    remove_old_timestamps(limiter)  # clean up before counting

    used = len(limiter["timestamps"])
    remaining = limiter["max_requests"] - used
    window = limiter["window_seconds"]

    print(f"  Used: {used} / {limiter['max_requests']} requests")
    print(f"  Remaining: {remaining} requests in this {window}s window")


# ---------------------------------------------------------------------------
# Demo — runs when you execute: python rate_limiter.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== Rate Limiter Demo ===\n")

    # Create a limiter: max 3 requests per 10 seconds
    limiter = create_rate_limiter(max_requests=3, window_seconds=10)

    # Try sending 5 requests back-to-back
    for i in range(1, 6):
        allowed = is_request_allowed(limiter)

        if allowed:
            record_request(limiter)         # consume the slot
            print(f"Request {i}: ✅ ALLOWED")
        else:
            print(f"Request {i}: ❌ DENIED — rate limit hit")

        get_status(limiter)
        print()

def is_request_allowed(limiter):
    remove_old_timestamps(limiter)   # step 1: clean up old entries
    # step 2: count active timestamps with len()
    # step 3: compare to limiter["max_requests"]
    # step 4: return True or False