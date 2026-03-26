# event_bus.py
#
# A publish-subscribe (pub-sub) system.
#
# The big idea:
#   - "Publishers" send out events  (e.g. "user just logged in")
#   - "Subscribers" register functions that run when an event fires
#   - Publishers and subscribers never talk directly — the EventBus is the middleman


class EventBus:
    """
    The central hub that connects publishers and subscribers.
    Think of it like a radio tower:
      - Subscribers "tune in" to a channel (the event name)
      - Publishers "broadcast" on a channel with some data
      - Every subscriber tuned to that channel receives the broadcast
    """

    def __init__(self):
        # self.subscribers is a dictionary where:
        #   key   = event name (a string like "user.login" or "task.added")
        #   value = a list of callback functions to call when that event fires
        #
        # Example after a few subscriptions:
        #   {
        #       "user.login":  [send_welcome_email, log_activity],
        #       "task.added":  [refresh_ui],
        #       "user.*":      [audit_logger],   # wildcard — matches any user.X
        #   }
        self.subscribers = {}

    def subscribe(self, event_name, callback):
        """Register a function to be called whenever a specific event fires."""
        # If this event name hasn't been seen before, create an empty list for it
        if event_name not in self.subscribers:
            self.subscribers[event_name] = []

        # Add the callback — multiple functions can subscribe to the same event
        self.subscribers[event_name].append(callback)
        print(f"  [+] '{callback.__name__}' subscribed to '{event_name}'")

    def unsubscribe(self, event_name, callback):
        """Remove a previously registered callback so it stops receiving events."""
        if event_name not in self.subscribers:
            print(f"  [-] No subscribers found for '{event_name}'")
            return

        # .remove() raises ValueError if the item isn't in the list, so we catch it
        try:
            self.subscribers[event_name].remove(callback)
            print(f"  [-] '{callback.__name__}' unsubscribed from '{event_name}'")
        except ValueError:
            print(f"  [-] '{callback.__name__}' was not subscribed to '{event_name}'")
            return

        # Clean up: remove the key entirely if the list is now empty
        if len(self.subscribers[event_name]) == 0:
            del self.subscribers[event_name]

    def _matches_wildcard(self, pattern, event_name):
        """
        Check whether a wildcard pattern matches an event name.
        Rules:
          - "user.*"  matches "user.login", "user.logout" — but NOT "admin.login"
          - "*.click" matches "button.click", "link.click"
          - "user.*"  does NOT match "user.login.extra"  (different segment count)
        """
        if "*" not in pattern:
            return pattern == event_name

        # Split on "." to get segments:
        # "user.*"     → ["user", "*"]
        # "user.login" → ["user", "login"]
        pattern_parts = pattern.split(".")
        event_parts   = event_name.split(".")

        # Different number of segments = no match
        if len(pattern_parts) != len(event_parts):
            return False

        # Compare each segment — "*" accepts anything
        for pattern_seg, event_seg in zip(pattern_parts, event_parts):
            if pattern_seg == "*":
                continue
            if pattern_seg != event_seg:
                return False
        return True

    def publish(self, event_name, data=None):
        """
        Fire an event — call every subscriber whose pattern matches.

        event_name : the event being fired (e.g. "user.login")
        data       : optional info to pass along (e.g. {"username": "alice"})
        """
        # ✏️  YOUR TURN — implement this method!
        #
        # Step 1: Create an empty list to collect matching callbacks:
        #           matching_callbacks = []
        #
        # Step 2: Loop over self.subscribers like this:
        #           for pattern, callbacks in self.subscribers.items():
        #         For each pattern, check if EITHER of these is True:
        #           a) pattern == event_name
        #           b) self._matches_wildcard(pattern, event_name)
        #         If so, add that event's callbacks to your list:
        #           matching_callbacks.extend(callbacks)
        #
        # Step 3: If matching_callbacks is still empty, print a notice and return
        #
        # Step 4: Loop through matching_callbacks and call each one:
        #           callback(event_name, data)
        #
        pass

def on_user_login(event, data):
    print(f"    → on_user_login:      event='{event}'  data={data}")

def on_any_user_event(event, data):
    print(f"    → on_any_user_event:  event='{event}'  data={data}")

def on_task_added(event, data):
    print(f"    → on_task_added:      event='{event}'  data={data}")

bus = EventBus()
bus.subscribe("user.login", on_user_login)
bus.subscribe("user.*",     on_any_user_event)   # wildcard
bus.subscribe("task.added", on_task_added)

print("\n-- publish user.login --")
bus.publish("user.login", {"username": "alice"})

print("\n-- publish task.added --")
bus.publish("task.added", {"task": "Buy milk"})

print("\n-- publish unknown.event --")
bus.publish("unknown.event")