import fnmatch


class EventBus:
    """A simple publish-subscribe event bus with wildcard support."""

    def __init__(self):
        # Dictionary to store subscriptions
        # Key: event pattern (e.g., "user.created" or "user.*")
        # Value: list of handler functions to call when event is published
        self.subscribers = {}

    def subscribe(self, event_pattern, handler):
        """
        Subscribe to an event or event pattern.

        Args:
            event_pattern: The event name or pattern (e.g., "user.created" or "user.*")
            handler: A function to call when matching event is published.
                    Handler receives (event_name, data) as arguments.
        """
        # If we haven't seen this pattern before, create empty list
        if event_pattern not in self.subscribers:
            self.subscribers[event_pattern] = []

        # Add this handler to the list for this pattern
        self.subscribers[event_pattern].append(handler)

    def unsubscribe(self, event_pattern, handler):
        """
        Unsubscribe from an event pattern.

        Args:
            event_pattern: The event pattern to unsubscribe from
            handler: The specific handler function to remove

        Returns:
            True if handler was found and removed, False otherwise
        """
        # Check if pattern exists
        if event_pattern not in self.subscribers:
            return False

        # Try to remove the handler
        if handler in self.subscribers[event_pattern]:
            self.subscribers[event_pattern].remove(handler)

            # If no more handlers for this pattern, delete the pattern
            if len(self.subscribers[event_pattern]) == 0:
                del self.subscribers[event_pattern]

            return True

        return False

    def publish(self, event_name, data=None):
        """
        Publish an event to all matching subscribers.

        Args:
            event_name: The name of the event (e.g., "user.created")
            data: Any data to pass to the handlers (dict, string, etc.)

        Returns:
            Number of handlers that were called
        """
        handlers_called = 0

        # Loop through all subscribed patterns
        for pattern, handlers in self.subscribers.items():
            # fnmatch lets us use wildcards: * matches any sequence, ? matches one char
            if fnmatch.fnmatch(event_name, pattern):
                # Call each handler that matches this pattern
                for handler in handlers:
                    handler(event_name, data)
                    handlers_called += 1

        return handlers_called

    def get_subscribers(self):
        """Return a summary of all current subscriptions."""
        return {pattern: len(handlers) for pattern, handlers in self.subscribers.items()}

    def clear(self):
        """Remove all subscriptions."""
        self.subscribers.clear()

# Create the event bus
bus = EventBus()

# Define handler functions
def on_user_created(event_name, data):
    print(f"New user: {data['username']}")

def on_any_user_event(event_name, data):
    print(f"User event occurred: {event_name}")

# Subscribe to events
bus.subscribe("user.created", on_user_created)        # Specific event
bus.subscribe("user.*", on_any_user_event)            # Wildcard pattern

# Publish events
bus.publish("user.created", {"username": "alice"})     # Calls both handlers
bus.publish("user.updated", {"username": "bob"})       # Calls only wildcard handler
bus.publish("admin.login", {"admin": "charlie"})       # No handlers called

# Unsubscribe when done
bus.unsubscribe("user.created", on_user_created)

# Check subscriptions
print(bus.get_subscribers())  # {'user.*': 1}