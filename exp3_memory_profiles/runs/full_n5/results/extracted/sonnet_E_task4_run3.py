# event_bus.py
#
# A publish-subscribe (pub/sub) event system.
#
# HOW IT WORKS:
#   - Different parts of your program can "subscribe" to events they care about.
#   - Other parts can "publish" events when something happens.
#   - Subscribers get called automatically — they don't need to check anything.
#
# REAL-WORLD ANALOGY:
#   Think of a newsletter. Readers subscribe to topics they like.
#   When the publisher sends a new issue, only subscribed readers get it.

import fnmatch  # Built-in Python tool for wildcard pattern matching (e.g. "user.*")


# A "class" is a blueprint for creating objects that bundle data
# AND the functions that work on that data together.
# Think of it like defining a custom data type yourself.

class EventBus:
    """
    EventBus lets parts of your program talk to each other
    without knowing about each other directly.
    """

    def __init__(self):
        # __init__ runs automatically when you do: bus = EventBus()
        # It sets up the starting state of the object.

        # self.subscribers is a dictionary.
        # Keys   = event name patterns  (e.g. "user.login"  or  "user.*")
        # Values = lists of functions to call when that pattern fires
        #
        # After a few subscriptions it might look like:
        #   {
        #       "user.login":  [greet_user, log_activity],
        #       "user.*":      [track_all_user_events],
        #       "*.error":     [send_alert],
        #   }
        self.subscribers = {}

    # ─────────────────────────────────────────
    # SUBSCRIBE
    # ─────────────────────────────────────────

    def subscribe(self, event_name, handler):
        """
        Register a function to be called when a matching event fires.

        event_name : the pattern to listen for, e.g. "user.login" or "order.*"
        handler    : the function to call — it must accept (event_name, data)
        """

        # If this pattern has never been seen before, create an empty list for it
        if event_name not in self.subscribers:
            self.subscribers[event_name] = []

        # Append the handler function to the list for this pattern
        self.subscribers[event_name].append(handler)

        print(f"  ✅ Subscribed '{handler.__name__}' to '{event_name}'")

    # ─────────────────────────────────────────
    # PUBLISH
    # ─────────────────────────────────────────

    def publish(self, event_name, data=None):
        """
        Fire an event. Every handler whose pattern matches event_name
        will be called with (event_name, data).

        event_name : the specific event that happened, e.g. "user.login"
        data       : any Python value — a dict, string, number, list, etc.
                     Defaults to None if you have nothing extra to share.
        """

        print(f"\n📢  Publishing '{event_name}'  |  data={data}")

        # Track how many handlers we actually called
        handlers_called = 0

        # Loop over every registered pattern and its list of handlers.
        # .items() gives us both the key (pattern) and value (handlers) at once.
        for pattern, handlers in self.subscribers.items():

            # fnmatch.fnmatch() checks whether event_name matches the pattern.
            #
            # Examples:
            #   fnmatch.fnmatch("user.login",   "user.*")   → True
            #   fnmatch.fnmatch("order.placed", "user.*")   → False
            #   fnmatch.fnmatch("db.error",     "*.error")  → True
            #   fnmatch.fnmatch("user.login",   "user.login") → True (exact match)
            if fnmatch.fnmatch(event_name, pattern):

                # This pattern matches — call every handler registered for it
                for handler in handlers:
                    print(f"    → calling '{handler.__name__}' (matched '{pattern}')")
                    handler(event_name, data)  # Pass the event name AND the data
                    handlers_called += 1

        # Helpful notice if nothing was listening for this event
        if handlers_called == 0:
            print(f"    (no subscribers matched '{event_name}')")

    # ─────────────────────────────────────────
    # UNSUBSCRIBE  ← YOUR TURN TO IMPLEMENT!
    # ─────────────────────────────────────────

    def unsubscribe(self, event_name, handler):
        """
        Remove a previously registered handler so it no longer gets called.

        event_name : the exact pattern string used when subscribing
        handler    : the exact same function object that was registered

        ┌─────────────────────────────────────────────────────────────┐
        │  TODO: Implement this method!                               │
        │                                                             │
        │  Step 1 — Check if event_name is in self.subscribers.      │
        │           If it's not there, decide:                        │
        │             • Raise a KeyError  (fail loud — reveals bugs)  │
        │             • Silently return   (fail soft — easy for caller)│
        │                                                             │
        │  Step 2 — Remove handler from the list.                    │
        │           Hint: Python lists have a .remove() method.       │
        │           But .remove() raises ValueError if not found —    │
        │           decide whether to let that crash or catch it.     │
        │                                                             │
        │  Step 3 (Bonus) — If the list is now empty after removing, │
        │           delete the key entirely to keep things tidy:      │
        │             del self.subscribers[event_name]                │
        │                                                             │
        │  Trade-off:                                                  │
        │    Most real systems choose "fail soft" for unsubscribe     │
        │    because unsubscribing twice shouldn't crash your app.    │
        │                                                             │
        │  When working, this should print something like:           │
        │    "  ❌ Unsubscribed 'my_fn' from 'user.login'"            │
        └─────────────────────────────────────────────────────────────┘
        """
        pass  # ← Replace this with your implementation

    # ─────────────────────────────────────────
    # HELPER
    # ─────────────────────────────────────────

    def list_subscriptions(self):
        """Print all active subscriptions. Great for debugging."""
        print("\n📋  Active subscriptions:")
        if not self.subscribers:
            print("    (none)")
            return
        for pattern, handlers in self.subscribers.items():
            # Build a comma-separated list of function names
            names = ", ".join(h.__name__ for h in handlers)
            print(f"    '{pattern}'  →  [{names}]")
        print()

# example.py
#
# A demo of the EventBus using a mini to-do app scenario.
# Run this file to see publish-subscribe in action.

from event_bus import EventBus


# ── Define some handler functions ─────────────────────────────────────────────
# Each handler receives two arguments:
#   event_name : the exact event that fired (e.g. "todo.added")
#   data       : whatever the publisher passed along (could be anything)

def on_todo_added(event_name, data):
    # This runs whenever a todo is added
    print(f"      [TodoList] New task: '{data['title']}'")

def on_todo_completed(event_name, data):
    print(f"      [TodoList] Marked done: '{data['title']}'")

def log_everything(event_name, data):
    # This uses a wildcard — it fires for ANY "todo.*" event
    print(f"      [Logger]   Event logged: {event_name}")

def send_notification(event_name, data):
    print(f"      [Notifier] 🔔 You have a new event: {event_name}")


# ── Create an EventBus ─────────────────────────────────────────────────────────
bus = EventBus()  # Creates a new EventBus object using our class blueprint

print("=== Subscribing ===")

# Subscribe specific handlers to specific events
bus.subscribe("todo.added",     on_todo_added)
bus.subscribe("todo.completed", on_todo_completed)

# Subscribe a wildcard handler — fires for ANY event starting with "todo."
bus.subscribe("todo.*",         log_everything)

# Subscribe to ALL events using the * wildcard
bus.subscribe("*",              send_notification)

bus.list_subscriptions()


# ── Publish some events ────────────────────────────────────────────────────────
print("=== Publishing ===")

bus.publish("todo.added",     {"title": "Buy groceries", "priority": "high"})
bus.publish("todo.completed", {"title": "Buy groceries"})
bus.publish("todo.deleted",   {"title": "Buy groceries"})  # only wildcard handlers fire
bus.publish("app.started",    {"version": "1.0"})          # only "*" handler fires


# ── Test unsubscribe (once you implement it!) ──────────────────────────────────
print("\n=== Testing Unsubscribe ===")
bus.unsubscribe("todo.added", on_todo_added)

# After unsubscribing, on_todo_added should NOT be called
bus.publish("todo.added", {"title": "Walk the dog"})

bus.list_subscriptions()

def unsubscribe(self, event_name, handler):
    # Step 1: Does the event_name even exist?
    if event_name not in self.subscribers:
        return  # or raise KeyError(f"No subscriptions for '{event_name}'")

    # Step 2: Remove the handler
    # ... your code here ...

    # Step 3 (bonus): Clean up empty lists
    # ... your code here ...

    print(f"  ❌ Unsubscribed '{handler.__name__}' from '{event_name}'")