import fnmatch
from typing import Callable, Any, Dict, List


class EventBus:
    """
    A publish-subscribe event system that manages event subscriptions and publications.
    
    Subscribers register callback functions for specific events, and when those events
    are published, all registered callbacks are called with the event data.
    """

    def __init__(self):
        """Initialize the event bus. _subscribers stores callbacks for each event."""
        self._subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_name: str, callback: Callable) -> int:
        """
        Register a callback for an event.

        Args:
            event_name: The event name (e.g. "user.created"). Can use wildcards like "user.*"
            callback: Function to call when event is published. Receives event data.

        Returns:
            subscription_id: Unique ID for this subscription
        """
        # Create empty list if event hasn't been subscribed to yet
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []

        # Add callback to the subscribers list
        self._subscribers[event_name].append(callback)

        # Return subscription ID
        return id(callback)

    def unsubscribe(self, event_name: str, callback: Callable) -> bool:
        """
        Remove a callback from an event.

        Args:
            event_name: The event to unsubscribe from
            callback: The callback function to remove

        Returns:
            bool: True if removed, False if callback not found
        """
        # Return False if event has no subscribers
        if event_name not in self._subscribers:
            return False

        try:
            # Remove callback from list
            self._subscribers[event_name].remove(callback)

            # Clean up empty event entries
            if not self._subscribers[event_name]:
                del self._subscribers[event_name]

            return True
        except ValueError:
            # Callback wasn't in list
            return False

    def publish(self, event_name: str, data: Any = None) -> int:
        """
        Publish an event and trigger all matching callbacks.

        Args:
            event_name: The event name to publish (e.g. "user.created")
            data: Optional data to pass to subscribers

        Returns:
            int: Number of callbacks triggered
        """
        callbacks_triggered = 0

        # Check all registered event patterns
        for subscribed_event, callbacks in self._subscribers.items():
            # Use wildcard matching to check if pattern matches published event
            if self._event_matches(subscribed_event, event_name):
                # Call each matching callback
                for callback in callbacks:
                    try:
                        callback(data)
                        callbacks_triggered += 1
                    except Exception as e:
                        # Print error but continue with other callbacks
                        print(f"Error in callback for '{subscribed_event}': {e}")

        return callbacks_triggered

    def _event_matches(self, pattern: str, event_name: str) -> bool:
        """
        Check if an event name matches a subscription pattern.

        Uses fnmatch for Unix shell-style wildcards:
        - * matches everything
        - ? matches single character
        - [seq] matches any character in seq

        Examples:
            - "user.created" matches "user.created" (exact)
            - "user.*" matches "user.created" and "user.deleted" (wildcard)
        """
        return fnmatch.fnmatch(event_name, pattern)

    def get_subscriber_count(self, event_name: str = None) -> int:
        """
        Get number of subscribers for an event or total subscribers.

        Args:
            event_name: Specific event to count (optional). If None, counts all.

        Returns:
            int: Number of subscribers
        """
        if event_name is None:
            # Sum subscribers across all events
            return sum(len(callbacks) for callbacks in self._subscribers.values())

        # Count for specific event
        return len(self._subscribers.get(event_name, []))

    def clear(self, event_name: str = None) -> None:
        """
        Clear subscribers for an event or entire bus.

        Args:
            event_name: Specific event to clear (optional). If None, clears all.
        """
        if event_name is None:
            # Clear everything
            self._subscribers.clear()
        elif event_name in self._subscribers:
            # Clear specific event
            del self._subscribers[event_name]

if __name__ == "__main__":
    bus = EventBus()

    # Define callbacks
    def on_user_created(data):
        print(f"New user: {data['name']}")

    def on_any_user_event(data):
        print(f"User event: {data}")

    # Subscribe to events
    bus.subscribe("user.created", on_user_created)
    bus.subscribe("user.*", on_any_user_event)  # Catches ALL user.* events

    # Publish events
    bus.publish("user.created", {"id": 1, "name": "Alice"})
    # Output:
    # New user: Alice
    # User event: {'id': 1, 'name': 'Alice'}

    bus.publish("user.deleted", {"id": 2, "name": "Bob"})
    # Output:
    # User event: {'id': 2, 'name': 'Bob'}  <- only wildcard matches

    # Unsubscribe
    bus.unsubscribe("user.created", on_user_created)

    # Check subscriber count
    print(bus.get_subscriber_count())  # 1 (just the wildcard)
    print(bus.get_subscriber_count("user.*"))  # 1