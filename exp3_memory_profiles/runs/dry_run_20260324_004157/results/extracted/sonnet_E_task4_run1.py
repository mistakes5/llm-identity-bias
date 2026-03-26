# event_bus.py — A publish-subscribe event system
#
# PUB-SUB IN A NUTSHELL:
#   Some code PUBLISHES events: "Hey, a to-do was just created!"
#   Other code SUBSCRIBES:      "Tell me whenever a to-do is created."
#   The EventBus sits in the middle, passing messages along.
#
# WHY USE THIS?
#   Without pub-sub your to-do app looks like:
#       add_todo(item)
#       update_ui(item)       # tight — every file knows about every other file
#       save_to_file(item)
#
#   With pub-sub:
#       add_todo(item)
#       bus.publish("todo.created", item)  # done! listeners handle the rest

import fnmatch   # Built-in Python module — handles wildcard patterns like "todo.*"


# ─────────────────────────────────────────────────────────────────────────────
# WHAT IS A CLASS?
# A class is a blueprint for creating objects. Think of it like a recipe card:
#   - The recipe (class) says what ingredients and steps exist.
#   - Each time you "make" the recipe, you get one fresh dish (instance).
# Here, EventBus is the recipe. You create one with:  bus = EventBus()
# ─────────────────────────────────────────────────────────────────────────────

class EventBus:

    def __init__(self):
        # __init__ runs automatically the moment you write: bus = EventBus()
        # It's the "setup" step that runs before anything else.

        # self._subscribers is a dictionary.
        # Keys   = event name patterns, e.g. "todo.created" or "todo.*"
        # Values = lists of functions to call when that pattern matches
        #
        # Example after a few subscribe() calls:
        # {
        #     "todo.created": [save_to_file, send_notification],
        #     "todo.*":       [update_ui],
        # }
        self._subscribers = {}

    # ──────────────────────────────────────────────────────────────────────────
    # SUBSCRIBE
    # ──────────────────────────────────────────────────────────────────────────
    def subscribe(self, event_name, callback):
        """
        Register a function to be called when a matching event is published.

        event_name : the pattern to listen for, e.g. "todo.created"
                     Wildcards work too: "todo.*" matches all todo events.
        callback   : any function — it will be called as callback(event_name, data)
        """

        # If nobody has subscribed to this pattern yet, create an empty list
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []

        # Add this function to the list for that pattern
        self._subscribers[event_name].append(callback)

        print(f"  [bus] subscribed '{callback.__name__}' to '{event_name}'")

    # ──────────────────────────────────────────────────────────────────────────
    # UNSUBSCRIBE
    # ──────────────────────────────────────────────────────────────────────────
    def unsubscribe(self, event_name, callback):
        """
        Remove a function so it stops receiving events.

        event_name : the same pattern used when subscribing
        callback   : the exact function object that was passed to subscribe()
        """

        # Guard: nobody subscribed to this pattern at all
        if event_name not in self._subscribers:
            print(f"  [bus] warning: no subscribers found for '{event_name}'")
            return

        # Guard: this specific function isn't in the list
        if callback not in self._subscribers[event_name]:
            print(f"  [bus] warning: '{callback.__name__}' wasn't subscribed to '{event_name}'")
            return

        # Remove the function from the list
        self._subscribers[event_name].remove(callback)
        print(f"  [bus] unsubscribed '{callback.__name__}' from '{event_name}'")

        # Housekeeping: if the list is now empty, remove the key too
        if not self._subscribers[event_name]:
            del self._subscribers[event_name]

    # ──────────────────────────────────────────────────────────────────────────
    # PUBLISH  <-- YOUR TURN!
    # ──────────────────────────────────────────────────────────────────────────
    def publish(self, event_name, data=None):
        """
        Fire an event. Every subscriber whose pattern matches event_name
        will have their callback function called immediately.

        event_name : the specific event that just happened, e.g. "todo.created"
        data       : any value to pass along (a string, dict, list, anything).
                     Defaults to None if you have nothing extra to send.
        """

        print(f"\n  [bus] publishing '{event_name}' ...")

        # ── TODO: your implementation goes here ───────────────────────────────
        #
        # STEP 1 — Loop over every stored pattern and its callbacks:
        #
        #     for pattern, callbacks in self._subscribers.items():
        #
        #   (dict.items() gives you each key-value pair at the same time)
        #
        # STEP 2 — Inside the loop, check if event_name matches the pattern:
        #
        #     if fnmatch.fnmatch(event_name, pattern):
        #
        #   fnmatch handles wildcards automatically:
        #     fnmatch.fnmatch("todo.created", "todo.*")      -> True
        #     fnmatch.fnmatch("todo.created", "todo.created")-> True
        #     fnmatch.fnmatch("todo.created", "user.*")      -> False
        #
        # STEP 3 — If it matches, loop over each callback and call it:
        #
        #     for callback in callbacks:
        #         callback(event_name, data)
        #
        # BONUS — add a print so you can see what's happening:
        #
        #     print(f"    -> calling '{callback.__name__}'")
        #
        # Your finished publish() should be about 5-8 lines. Give it a go!
        # ─────────────────────────────────────────────────────────────────────

        pass   # <-- delete this line and write your code here

    # ──────────────────────────────────────────────────────────────────────────
    # HELPER — see all current subscriptions (handy for debugging)
    # ──────────────────────────────────────────────────────────────────────────
    def list_subscribers(self):
        """Print a summary of who is subscribed to what."""
        print("\n  [bus] current subscriptions:")
        if not self._subscribers:
            print("    (none)")
            return
        for pattern, callbacks in self._subscribers.items():
            names = [cb.__name__ for cb in callbacks]   # grab the name of each function
            print(f"    '{pattern}' -> {names}")

# demo.py — test the EventBus with a simple to-do scenario

from event_bus import EventBus

# ── Create the bus ──────────────────────────────────────────────────────────
bus = EventBus()

# ── Define some listener functions ──────────────────────────────────────────
# Each one receives the event name and whatever data was published.

def save_to_file(event, data):
    print(f"    [save_to_file]  saving '{data}' because of '{event}'")

def update_ui(event, data):
    print(f"    [update_ui]     refreshing screen because of '{event}'")

def send_notification(event, data):
    print(f"    [notification]  buzz! '{data}' was just {event.split('.')[1]}")

# ── Subscribe ────────────────────────────────────────────────────────────────
print("\n--- subscribing ---")
bus.subscribe("todo.created",  save_to_file)
bus.subscribe("todo.created",  send_notification)
bus.subscribe("todo.*",        update_ui)       # wildcard: matches ANY todo event

bus.list_subscribers()

# ── Publish ──────────────────────────────────────────────────────────────────
print("\n--- publishing ---")
bus.publish("todo.created",  "Buy groceries")
bus.publish("todo.deleted",  "Old task")        # only update_ui should fire (wildcard)
bus.publish("user.logged_in", "alice")          # no subscribers — nothing should fire

# ── Unsubscribe and publish again ────────────────────────────────────────────
print("\n--- after unsubscribing send_notification ---")
bus.unsubscribe("todo.created", send_notification)
bus.list_subscribers()
bus.publish("todo.created", "Walk the dog")     # notification should no longer fire