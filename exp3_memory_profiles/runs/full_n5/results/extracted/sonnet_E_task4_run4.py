# pub_sub.py
# A publish-subscribe ("pub/sub") event system in Python.
#
# The idea:
#   - Code can "subscribe" to an event by name (e.g. "user.login")
#   - Other code can "publish" that event with some data
#   - Every subscribed function gets called automatically with that data
#   - Wildcards like "user.*" let you catch a whole category of events at once

import fnmatch  # Built-in Python module — handles wildcard patterns like "user.*"


# This dictionary is our "registry" of all current subscriptions.
#
# Structure:
#   {
#     "user.login":  [func_a, func_b],   ← two listeners for this exact event
#     "user.*":      [func_c],            ← one listener using a wildcard
#     "*":           [func_d],            ← one listener for ALL events
#   }
subscribers = {}


def subscribe(event_name, callback):
    if event_name not in subscribers:
        subscribers[event_name] = []
    subscribers[event_name].append(callback)
    print(f"  ✓  Subscribed '{callback.__name__}' to '{event_name}'")


def unsubscribe(event_name, callback):
    if event_name not in subscribers:
        print(f"  ✗  Nothing is subscribed to '{event_name}'")
        return
    if callback not in subscribers[event_name]:
        print(f"  ✗  '{callback.__name__}' was never subscribed to '{event_name}'")
        return
    subscribers[event_name].remove(callback)
    print(f"  ✓  Unsubscribed '{callback.__name__}' from '{event_name}'")
    if len(subscribers[event_name]) == 0:
        del subscribers[event_name]


def _matches_pattern(event_name, pattern):
    """
    Return True if the published event_name matches a subscription pattern.

    Examples:
        "user.login"    vs "user.login"   → True   (exact match)
        "user.login"    vs "user.*"       → True   (wildcard match)
        "user.login"    vs "*.login"      → True   (wildcard at the front)
        "order.placed"  vs "user.*"       → False  (different prefix)
        "anything"      vs "*"            → True   (catch-all wildcard)
    """
    # 👉 YOUR TURN — implement this (1–3 lines)
    pass


def publish(event_name, data=None):
    print(f"\n📢  Publishing '{event_name}'  |  data = {data}")
    called_count = 0

    # Loop every subscription pattern and check if it matches
    for pattern, callbacks in subscribers.items():
        if _matches_pattern(event_name, pattern):
            for callback in callbacks:
                print(f"  → calling '{callback.__name__}'")
                callback(event_name, data)
                called_count += 1

    if called_count == 0:
        print(f"  (no subscribers matched '{event_name}')")

import fnmatch

fnmatch.fnmatch("user.login", "user.*")    # → True
fnmatch.fnmatch("user.login", "order.*")   # → False
fnmatch.fnmatch("user.login", "*")         # → True  (catch-all)
fnmatch.fnmatch("user.login", "user.login") # → True  (exact also works!)