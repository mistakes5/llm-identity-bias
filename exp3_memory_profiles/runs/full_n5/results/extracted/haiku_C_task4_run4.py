from typing import Callable, Any, Dict, List, Set
from dataclasses import dataclass
from fnmatch import fnmatch


@dataclass
class Event:
    """Represents an event with a name and associated data."""
    name: str
    data: Any = None

    def __repr__(self) -> str:
        return f"Event(name='{self.name}', data={self.data!r})"


class EventBus:
    """
    A publish-subscribe event bus supporting wildcard subscriptions.

    Features:
    - Direct subscriptions: subscribe('user.login', callback)
    - Wildcard subscriptions: subscribe('user.*', callback)
    - Multiple subscribers per event
    - Unsubscribe support via returned function
    - Type-safe event data passing
    """

    def __init__(self):
        """Initialize the event bus with empty subscription maps."""
        self._direct_subscriptions: Dict[str, Set[Callable]] = {}
        self._wildcard_subscriptions: Dict[str, Set[Callable]] = {}

    def subscribe(self, event_pattern: str, callback: Callable[[Event], None]) -> Callable:
        """
        Subscribe to an event or wildcard pattern.

        Args:
            event_pattern: Event name or wildcard pattern (e.g., 'user.login' or 'user.*')
            callback: Function to call when matching event is published. Receives Event object.

        Returns:
            Unsubscribe function - call it to remove this subscription.

        Raises:
            TypeError: If callback is not callable.

        Example:
            bus = EventBus()
            
            def handler(event):
                print(f"Event: {event.name}, Data: {event.data}")
            
            unsub = bus.subscribe('user.login', handler)
            bus.publish('user.login', data={'user_id': 123})
            unsub()  # Unsubscribe
        """
        if not callable(callback):
            raise TypeError(f"Callback must be callable, got {type(callback)}")

        # Determine if this is a wildcard subscription
        is_wildcard = '*' in event_pattern or '?' in event_pattern

        subscriptions = (self._wildcard_subscriptions 
                        if is_wildcard 
                        else self._direct_subscriptions)

        # Create the set for this pattern if it doesn't exist
        if event_pattern not in subscriptions:
            subscriptions[event_pattern] = set()

        subscriptions[event_pattern].add(callback)

        # Return an unsubscribe function
        def unsubscribe():
            subscriptions[event_pattern].discard(callback)
            # Clean up empty sets to avoid memory leaks
            if not subscriptions[event_pattern]:
                del subscriptions[event_pattern]

        return unsubscribe

    def unsubscribe(self, event_pattern: str, callback: Callable) -> bool:
        """
        Unsubscribe a callback from an event pattern.

        Args:
            event_pattern: The event pattern to unsubscribe from
            callback: The callback function to remove

        Returns:
            True if callback was found and removed, False otherwise.
        """
        is_wildcard = '*' in event_pattern or '?' in event_pattern
        subscriptions = (self._wildcard_subscriptions 
                        if is_wildcard 
                        else self._direct_subscriptions)

        if event_pattern not in subscriptions:
            return False

        if callback in subscriptions[event_pattern]:
            subscriptions[event_pattern].remove(callback)
            if not subscriptions[event_pattern]:
                del subscriptions[event_pattern]
            return True

        return False

    def publish(self, event_name: str, data: Any = None) -> int:
        """
        Publish an event to all matching subscribers.

        Args:
            event_name: Name of the event to publish
            data: Optional data to pass to subscribers

        Returns:
            Number of subscribers that received the event.

        Raises:
            TypeError: If event_name is not a string.
        """
        if not isinstance(event_name, str):
            raise TypeError(f"Event name must be a string, got {type(event_name)}")

        event = Event(name=event_name, data=data)
        subscriber_count = 0

        # Call direct subscribers (exact match)
        if event_name in self._direct_subscriptions:
            for callback in self._direct_subscriptions[event_name]:
                try:
                    callback(event)
                    subscriber_count += 1
                except Exception as e:
                    print(f"Error in event handler for '{event_name}': {e}")
                    raise

        # Call wildcard subscribers (pattern match)
        for pattern, callbacks in self._wildcard_subscriptions.items():
            if fnmatch(event_name, pattern):
                for callback in callbacks:
                    try:
                        callback(event)
                        subscriber_count += 1
                    except Exception as e:
                        print(f"Error in wildcard handler for pattern '{pattern}': {e}")
                        raise

        return subscriber_count

    def get_subscribers(self, event_name: str) -> Dict[str, Any]:
        """
        Get all subscribers (direct and wildcard) for an event name.

        Useful for debugging and testing.

        Args:
            event_name: The event name to query

        Returns:
            Dict with 'direct', 'wildcard', and 'total' keys.
        """
        direct = list(self._direct_subscriptions.get(event_name, []))

        wildcard = []
        for pattern, callbacks in self._wildcard_subscriptions.items():
            if fnmatch(event_name, pattern):
                wildcard.extend(callbacks)

        return {
            'direct': direct,
            'wildcard': wildcard,
            'total': len(direct) + len(wildcard)
        }

    def clear(self):
        """Clear all subscriptions from the event bus."""
        self._direct_subscriptions.clear()
        self._wildcard_subscriptions.clear()

# Create the event bus
bus = EventBus()

# Example 1: Direct subscriptions
def on_login(event):
    print(f"User {event.data['user_id']} logged in")

def on_logout(event):
    print(f"User {event.data['user_id']} logged out")

bus.subscribe('user.login', on_login)
bus.subscribe('user.logout', on_logout)

bus.publish('user.login', data={'user_id': 123})   # Triggers on_login
bus.publish('user.logout', data={'user_id': 123})  # Triggers on_logout


# Example 2: Wildcard subscriptions
def on_user_event(event):
    print(f"User event: {event.name}")

bus.subscribe('user.*', on_user_event)

bus.publish('user.login', data={'user_id': 456})    # Matches user.* 
bus.publish('user.update', data={'user_id': 456})   # Matches user.*
bus.publish('user.delete', data={'user_id': 456})   # Matches user.*


# Example 3: Multiple subscribers
def logger(event):
    print(f"[LOG] {event.name}")

def analytics(event):
    print(f"[ANALYTICS] {event.name}")

bus.subscribe('order.created', logger)
bus.subscribe('order.created', analytics)
bus.publish('order.created', data={'order_id': 789})  # Both handlers called


# Example 4: Unsubscribing
unsub = bus.subscribe('temp.event', lambda e: print("Handler"))
bus.publish('temp.event')  # Prints "Handler"

unsub()  # Unsubscribe using returned function
bus.publish('temp.event')  # No output


# Example 5: Complex wildcard patterns
def on_error(event):
    print(f"Error: {event.name}")

bus.subscribe('*.error', on_error)
bus.publish('database.error', data={'code': 'DB001'})  # Matches *.error
bus.publish('api.error', data={'code': 'API001'})       # Matches *.error


# Example 6: Subscriber introspection
subs = bus.get_subscribers('user.login')
print(f"Total subscribers: {subs['total']}")
print(f"Direct: {len(subs['direct'])}, Wildcard: {len(subs['wildcard'])}")