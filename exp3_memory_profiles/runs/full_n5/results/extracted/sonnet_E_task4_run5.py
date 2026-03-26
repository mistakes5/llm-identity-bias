# event_bus.py
# ============================================================
# A Publish-Subscribe (Pub/Sub) Event System
# ============================================================
#
# WHAT IS PUB/SUB?
# Imagine a newsletter. People "subscribe" to topics they care about.
# When the publisher sends a newsletter, everyone subscribed gets it.
# That's exactly what this code does -- but for events in your program!
#
# WHY IS THIS USEFUL FOR YOUR TO-DO APP?
# When you add a task, multiple things might need to happen:
#   - Save the task to a file
#   - Update the display
#   - Log that a task was created
# Instead of calling all those functions manually in one place,
# each part of your app just "subscribes" to the "task.added" event!
# ============================================================

# fnmatch is a built-in Python module for matching patterns with wildcards.
# Example: fnmatch.fnmatch("task.added", "task.*")  --> True
import fnmatch


# ============================================================
# WHAT IS A CLASS?
# A class is like a blueprint for creating objects.
# An object bundles together related DATA and FUNCTIONS.
#
# Our EventBus bundles:
#   DATA:      self._subscribers  (a dictionary: who listens for what)
#   FUNCTIONS: subscribe(), publish(), unsubscribe()
# ============================================================
class EventBus:

    def __init__(self):
        # __init__ runs automatically when you write: bus = EventBus()
        # "self" refers to THIS specific object (the bus you just created).

        # _subscribers maps event patterns to lists of callback functions.
        # After a few subscriptions it might look like:
        # {
        #   "task.added":  [save_to_file, update_display],
        #   "task.*":      [log_all_task_events],
        #   "*":           [count_every_event],
        # }
        self._subscribers = {}

    # ----------------------------------------------------------
    def subscribe(self, event_name, callback):
        # If this is the first subscriber for this pattern,
        # create an empty list to hold their functions.
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []

        # Append this callback to the list for this event.
        # Multiple functions can subscribe to the same event!
        self._subscribers[event_name].append(callback)

        # callback.__name__ is a built-in attribute: the function's name as text.
        print(f"[EventBus] '{callback.__name__}' subscribed to '{event_name}'")

    # ----------------------------------------------------------
    def unsubscribe(self, event_name, callback):
        # Safety check: does anyone subscribe to this pattern at all?
        if event_name not in self._subscribers:
            print(f"[EventBus] Warning: no subscriptions found for '{event_name}'")
            return  # "return" with no value just exits the function early

        # list.remove() raises a ValueError if the item isn't in the list.
        # We use try/except to catch that and show a friendly message instead of crashing.
        try:
            self._subscribers[event_name].remove(callback)
            print(f"[EventBus] '{callback.__name__}' unsubscribed from '{event_name}'")

            # Clean-up: if the list is now empty, remove the key entirely
            if len(self._subscribers[event_name]) == 0:
                del self._subscribers[event_name]

        except ValueError:
            # This block only runs if .remove() fails (callback wasn't in the list)
            print(f"[EventBus] Warning: '{callback.__name__}' was not subscribed to '{event_name}'")

    # ----------------------------------------------------------
    def publish(self, event_name, data=None):
        # Default to an empty dictionary if no data was provided.
        # (We can't write data={} as a default -- that's a Python gotcha with
        #  mutable defaults. Using None and replacing it here is the safe way.)
        if data is None:
            data = {}

        print(f"\n[EventBus] Publishing '{event_name}' | data: {data}")

        # Track how many callbacks we actually called.
        notified_count = 0

        # Loop through every registered subscription pattern.
        # dict.items() gives us both the key and value at the same time.
        for pattern, callbacks in self._subscribers.items():

            # Ask our matching engine: does this pattern fit the event?
            if self._matches(pattern, event_name):

                # Call every function that subscribed to this pattern.
                for callback in callbacks:
                    callback(data)          # pass the event data to the subscriber
                    notified_count += 1

        if notified_count == 0:
            print(f"[EventBus] (no subscribers matched '{event_name}')")

    # ----------------------------------------------------------
    def _matches(self, pattern, event_name):
        """
        Decide whether a subscription pattern matches a published event name.
        This is the "wildcard engine" -- YOUR CODE GOES HERE!

        EXAMPLES OF WHAT WE WANT:
            _matches("task.added",   "task.added")   --> True   (exact match)
            _matches("task.*",       "task.added")   --> True   (wildcard)
            _matches("task.*",       "task.deleted") --> True   (wildcard)
            _matches("*",            "task.added")   --> True   (catch-all)
            _matches("user.*",       "task.added")   --> False  (wrong namespace)
            _matches("task.added",   "task.deleted") --> False  (no match)

        ── YOUR CODE GOES HERE ────────────────────────────────────────────
        You need to return True or False. Pick one of these options:

        OPTION A -- Exact match only (simplest, no wildcards):
            return pattern == event_name

        OPTION B -- Wildcards via fnmatch (handles * automatically):
            return fnmatch.fnmatch(event_name, pattern)

        OPTION C -- Exact match first, then fall back to fnmatch (fastest):
            if pattern == event_name:
                return True
            return fnmatch.fnmatch(event_name, pattern)

        TRADE-OFFS:
          Option A: Fast and predictable -- but "task.*" will NOT work.
          Option B: Wildcards just work. Note "task*" (no dot) would also
                    match "taskforce.updated" which might surprise you.
          Option C: Best of both -- exact matches skip the fnmatch call entirely.
        ───────────────────────────────────────────────────────────────────
        """
        pass   # <-- replace this line with your return statement!

    # ----------------------------------------------------------
    def list_subscriptions(self):
        """Print all active subscriptions -- great for debugging."""
        if not self._subscribers:
            print("[EventBus] No active subscriptions.")
            return

        print("\n[EventBus] Active subscriptions:")
        for pattern, callbacks in self._subscribers.items():
            # List comprehension: compact way to build a list from a loop.
            # Same as: names = []; for cb in callbacks: names.append(cb.__name__)
            names = [cb.__name__ for cb in callbacks]
            print(f"  '{pattern}'  -->  {names}")

# demo.py
# Demonstrates the EventBus using a to-do app scenario.
# Run this with: python demo.py

from event_bus import EventBus

# Create our single shared event bus
bus = EventBus()


# ── Define subscriber functions ──────────────────────────────
# These are the functions that will be called when events fire.
# Each one receives a "data" dictionary with event details.

def save_task_to_file(data):
    # .get() safely reads a key -- returns "unnamed" if "name" doesn't exist
    print(f"  [saver]   Saving '{data.get('name', 'unnamed')}' to file...")

def update_display(data):
    print(f"  [display] Refreshing screen with new task: '{data.get('name', 'unnamed')}'")

def log_all_task_events(data):
    # This uses a wildcard -- it catches ALL task.* events
    print(f"  [logger]  Task event recorded: {data}")

def count_all_events(data):
    # This uses "*" -- it catches literally every event
    print(f"  [counter] Total event count +1")


# ── Subscribe to events ──────────────────────────────────────
print("=== Setting Up Subscriptions ===")
bus.subscribe("task.added",   save_task_to_file)
bus.subscribe("task.added",   update_display)
bus.subscribe("task.*",       log_all_task_events)   # wildcard: all task.X events
bus.subscribe("*",            count_all_events)      # wildcard: every single event

bus.list_subscriptions()


# ── Publish some events ──────────────────────────────────────
print("\n=== Publishing Events ===")

bus.publish("task.added",   {"name": "Buy groceries", "priority": "high"})
bus.publish("task.deleted", {"name": "Buy groceries"})
bus.publish("task.updated", {"name": "Buy groceries", "priority": "low"})
bus.publish("user.login",   {"username": "alice"})   # won't match "task.*"


# ── Unsubscribe and publish again ────────────────────────────
print("\n=== After Unsubscribing save_task_to_file ===")
bus.unsubscribe("task.added", save_task_to_file)

bus.publish("task.added", {"name": "Clean the house"})


# ── Edge case tests ──────────────────────────────────────────
print("\n=== Edge Cases ===")
bus.unsubscribe("task.added", save_task_to_file)   # already removed!
bus.unsubscribe("does.not.exist", save_task_to_file)
bus.publish("totally.unknown.event", {})            # nobody is listening