# rate_limiter.py
# A sliding-window rate limiter — tracks request timestamps and
# rejects requests that exceed the allowed limit.

import time  # the built-in time module lets us get the current time as a number

# -----------------------------------------------------------------------
# Settings — change these two numbers to control how strict the limiter is
# -----------------------------------------------------------------------
MAX_REQUESTS = 5          # how many requests are allowed...
TIME_WINDOW_SECONDS = 10  # ...within this many seconds

# -----------------------------------------------------------------------
# Storage
# -----------------------------------------------------------------------
# This list holds the timestamp of every recent request.
# A "timestamp" is a big decimal number — seconds since Jan 1, 1970.
#   Example: 1711234567.891
# As requests come in we append to this list. Old entries get removed
# so the list never grows forever.
request_timestamps = []   # starts empty


# -----------------------------------------------------------------------
# Helper: remove timestamps that have "expired"
# -----------------------------------------------------------------------
def _remove_old_timestamps():
    """
    Removes entries from request_timestamps that are older than
    TIME_WINDOW_SECONDS ago. After calling this, every timestamp
    left in the list is still "inside" the current window.
    """
    # TODO — implement this function! (about 5–7 lines)
    #
    # Steps:
    #   1. Tell Python you want to modify the global list:
    #        global request_timestamps
    #   2. Get the current time:
    #        current_time = time.time()
    #   3. Calculate the oldest timestamp you still want to keep:
    #        cutoff = current_time - TIME_WINDOW_SECONDS
    #      Anything *before* cutoff is outside the window and should go.
    #   4. Rebuild the list keeping only timestamps >= cutoff.
    #      Loop approach:
    #        fresh = []
    #        for ts in request_timestamps:
    #            if ts >= cutoff:
    #                fresh.append(ts)
    #        request_timestamps = fresh

    pass  # delete this line once you've written your code


# -----------------------------------------------------------------------
# Check: is this request allowed?
# -----------------------------------------------------------------------
def is_request_allowed():
    """
    Returns True if the request is within the rate limit, False if blocked.
    Side effect: if allowed, the current timestamp is recorded.
    """
    # Step 1 — throw out any timestamps that are too old
    _remove_old_timestamps()

    # Step 2 — count how many requests are still in the window
    if len(request_timestamps) < MAX_REQUESTS:
        # We're under the limit — record this moment and allow the request
        request_timestamps.append(time.time())  # time.time() = "right now"
        return True   # allowed!
    else:
        # We've used up all allowed requests for this window
        return False  # blocked!


# -----------------------------------------------------------------------
# Info: how many requests are counted right now?
# -----------------------------------------------------------------------
def get_request_count():
    """
    Returns the number of requests recorded in the current time window.
    Useful for showing "you've used X of Y requests".
    """
    _remove_old_timestamps()        # always clean up first for accuracy
    return len(request_timestamps)  # list length = number of recent requests


# -----------------------------------------------------------------------
# Utility: wipe everything and start fresh
# -----------------------------------------------------------------------
def reset():
    """
    Clears all recorded timestamps, resetting the limiter to zero.
    Handy for testing or for admin overrides.
    """
    global request_timestamps    # 'global' lets us reassign the variable itself
    request_timestamps = []      # replace with a brand-new empty list
    print("Rate limiter has been reset.")


# -----------------------------------------------------------------------
# Quick demo — only runs when you execute THIS file directly:
#   python rate_limiter.py
# -----------------------------------------------------------------------
if __name__ == "__main__":
    print(f"Settings: {MAX_REQUESTS} requests per {TIME_WINDOW_SECONDS} seconds\n")

    # Try 7 requests — the first 5 should be allowed, the last 2 blocked
    for i in range(1, 8):
        allowed = is_request_allowed()
        count   = get_request_count()
        status  = "ALLOWED" if allowed else "BLOCKED"
        print(f"Request {i}: {status}  (requests in window: {count}/{MAX_REQUESTS})")

    print("\n--- waiting 11 seconds so the window slides past ---")
    time.sleep(11)

    print("\nAfter the window expires:")
    allowed = is_request_allowed()
    print(f"Request 8: {'ALLOWED' if allowed else 'BLOCKED'}  (requests in window: {get_request_count()}/{MAX_REQUESTS})")

def _remove_old_timestamps():
    global request_timestamps          # line 1 — lets us modify the list

    current_time = time.time()         # line 2 — what time is it right now?
    cutoff = current_time - TIME_WINDOW_SECONDS  # line 3 — oldest time we care about

    # line 4–7: keep only the timestamps that are recent enough
    fresh = []
    for ts in request_timestamps:
        if ts >= cutoff:
            fresh.append(ts)
    request_timestamps = fresh