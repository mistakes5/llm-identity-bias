# Publish-Subscribe Event System
# A simple but powerful pub/sub implementation that allows publishers and subscribers
# to communicate through named events without tight coupling.

from typing import Callable, Any, Dict, List, Set


class EventSystem:
    """
    A publish-subscribe event system that allows multiple subscribers to listen
    for events and react when those events are published.

    Supports:
    - Direct subscriptions: subscribe to specific event names
    - Wildcard subscriptions: subscribe to event patterns (e.g., "user.*")
    """

    def __init__(self):
        """Initialize the event system with empty subscriber lists."""
        # Direct subscribers: maps event name -> list of callback functions
        self.subscribers: Dict[str, List[Callable]] = {}

        # Wildcard subscribers: stores patterns that can match multiple events
        self.wildcard_subscribers: Dict[str, List[Callable]] = {}

    def subscribe(self, event_name: str, callback: Callable) -> None:
        """
        Subscribe to an event. When the event is published, callback will be called
        with the event data.

        Args:
            event_name: Name of the event to subscribe to. Can be:
                       - A specific event like "user_login"
                       - A wildcard pattern like "user.*" to match "user_login", "user_logout", etc.
            callback: Function to call when event is published. Should accept one argument (the data).

        Example:
            def on_user_login(data):
                print(f"User {data['name']} logged in")

            system.subscribe("user_login", on_user_login)
            system.publish("user_login", {"name": "Alice"})  # Prints: User Alice logged in
        """
        # Check if this is a wildcard subscription (contains *)
        if "*" in event_name:
            # Store wildcard subscriptions separately for special handling
            if event_name not in self.wildcard_subscribers:
                self.wildcard_subscribers[event_name] = []
            self.wildcard_subscribers[event_name].append(callback)
        else:
            # Direct subscription - simple one-to-one mapping
            if event_name not in self.subscribers:
                self.subscribers[event_name] = []
            self.subscribers[event_name].append(callback)

    def unsubscribe(self, event_name: str, callback: Callable) -> bool:
        """
        Remove a subscription. The callback will no longer be called for this event.

        Args:
            event_name: The event name to unsubscribe from
            callback: The exact callback function to remove

        Returns:
            True if the callback was found and removed, False otherwise
        """
        # Determine which dictionary to search based on whether it's a wildcard
        if "*" in event_name:
            subscriber_dict = self.wildcard_subscribers
        else:
            subscriber_dict = self.subscribers

        # If the event has subscribers, try to remove the callback
        if event_name in subscriber_dict:
            if callback in subscriber_dict[event_name]:
                subscriber_dict[event_name].remove(callback)
                # Clean up empty lists to keep things tidy
                if not subscriber_dict[event_name]:
                    del subscriber_dict[event_name]
                return True

        return False

    def _matches_pattern(self, pattern: str, event_name: str) -> bool:
        """
        Check if an event name matches a wildcard pattern.

        This is where YOU come in! Implement the wildcard matching logic.

        Args:
            pattern: A pattern like "user.*" or "order.*.created"
            event_name: The actual event name like "user_login"

        Returns:
            True if event_name matches the pattern, False otherwise

        Examples:
            "user.*" should match "user_login", "user_logout", "user_created"
            "user.*" should NOT match "admin_login"
            "order.*.created" should match "order_1_created", "order_2_created"

        TODO: Replace the pass statement below with your implementation.
        Hint: Convert the pattern to a regular expression or use string operations.
        """
        pass

    def publish(self, event_name: str, data: Any = None) -> int:
        """
        Publish an event, notifying all subscribers (both direct and wildcard).

        Args:
            event_name: The name of the event being published
            data: Any data to pass to the subscribers (dict, string, number, etc.)

        Returns:
            The number of subscribers that were notified

        Example:
            count = system.publish("user_login", {"name": "Bob", "timestamp": 1234567890})
            print(f"Notified {count} subscribers")
        """
        notified_count = 0

        # 1. Notify direct subscribers (those listening to this exact event)
        if event_name in self.subscribers:
            for callback in self.subscribers[event_name]:
                try:
                    callback(data)
                    notified_count += 1
                except Exception as e:
                    # Print error but don't crash - let other subscribers run
                    print(f"Error in callback for '{event_name}': {e}")

        # 2. Notify wildcard subscribers (those listening to patterns)
        for pattern, callbacks in self.wildcard_subscribers.items():
            # Check if this event matches the pattern
            if self._matches_pattern(pattern, event_name):
                for callback in callbacks:
                    try:
                        callback(data)
                        notified_count += 1
                    except Exception as e:
                        print(f"Error in wildcard callback for pattern '{pattern}': {e}")

        return notified_count

    def get_subscribers(self, event_name: str) -> int:
        """
        Get the number of direct subscribers for an event.

        Args:
            event_name: The event name to check

        Returns:
            Number of callbacks subscribed to this event
        """
        return len(self.subscribers.get(event_name, []))

    def get_wildcard_subscribers(self, pattern: str) -> int:
        """Get the number of wildcard subscribers for a pattern."""
        return len(self.wildcard_subscribers.get(pattern, []))


# ============================================================================
# Example usage demonstrating the system
# ============================================================================

if __name__ == "__main__":
    # Create an event system
    events = EventSystem()

    # Define some callback functions (handlers for when events occur)
    def on_user_login(data):
        print(f"✓ Login handler: User '{data['username']}' logged in at {data['time']}")

    def on_user_event(data):
        print(f"  └─ Any user event caught: {data}")

    def on_order_created(data):
        print(f"✓ Order created: Order #{data['order_id']} from {data['customer']}")

    def on_any_order_event(data):
        print(f"  └─ Any order event caught: {data}")

    # Subscribe to specific events
    events.subscribe("user_login", on_user_login)
    events.subscribe("order_created", on_order_created)

    # Subscribe to wildcard patterns
    events.subscribe("user.*", on_user_event)
    events.subscribe("order.*", on_any_order_event)

    print("--- Publishing Events ---\n")

    # Publish a user login event
    print("1. Publishing user_login:")
    events.publish("user_login", {
        "username": "alice",
        "time": "2:30 PM"
    })

    print("\n2. Publishing user_logout:")
    events.publish("user_logout", {
        "username": "alice",
        "time": "5:00 PM"
    })

    print("\n3. Publishing order_created:")
    events.publish("order_created", {
        "order_id": 12345,
        "customer": "Bob"
    })

    print("\n4. Publishing order_shipped:")
    events.publish("order_shipped", {
        "order_id": 12345,
        "tracking": "TRK123456"
    })

    # Test unsubscribe
    print("\n--- Testing Unsubscribe ---\n")
    print("Unsubscribing from user.* pattern")
    events.unsubscribe("user.*", on_user_event)

    print("Publishing user_created (no wildcard handler anymore):")
    events.publish("user_created", {
        "username": "charlie",
        "email": "charlie@example.com"
    })

def _matches_pattern(self, pattern: str, event_name: str) -> bool:
    # Your code here!
    # Return True if event_name matches pattern, False otherwise