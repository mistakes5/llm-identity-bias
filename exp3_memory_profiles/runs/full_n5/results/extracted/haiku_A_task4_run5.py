"""
Publish-Subscribe Event System
Supports typed event subscriptions, pattern matching, and wildcard subscriptions.
"""

import fnmatch
from typing import Callable, Any, Dict
from dataclasses import dataclass
import threading


@dataclass
class Event:
    """Represents a published event with a name and associated data."""
    name: str
    data: Any = None

    def __repr__(self) -> str:
        return f"Event(name='{self.name}', data={self.data!r})"


class EventBus:
    """
    Thread-safe publish-subscribe event system supporting wildcard subscriptions.

    Examples:
        bus = EventBus()

        # Subscribe to specific event
        bus.subscribe("user.created", lambda evt: print(f"User created: {evt.data}"))

        # Subscribe to all user events (wildcard)
        bus.subscribe("user.*", lambda evt: print(f"User event: {evt.data}"))

        # Subscribe to all events
        bus.subscribe("*", lambda evt: print(f"Any event: {evt.data}"))

        # Publish an event
        bus.publish("user.created", {"id": 123, "email": "user@example.com"})
    """

    def __init__(self):
        self._subscribers: Dict[str, list[Callable]] = {}
        self._lock = threading.RLock()

    def subscribe(self, pattern: str, handler: Callable[[Event], None]) -> Callable[[], None]:
        """
        Subscribe a handler to events matching a pattern.

        Supports wildcards:
        - "event_name" matches only "event_name"
        - "user.*" matches "user.created", "user.deleted", etc.
        - "*" matches all events

        Args:
            pattern: Event pattern to subscribe to (supports fnmatch wildcards)
            handler: Callable that receives an Event object

        Returns:
            Unsubscribe function that removes this handler
        """
        with self._lock:
            if pattern not in self._subscribers:
                self._subscribers[pattern] = []
            self._subscribers[pattern].append(handler)

        def unsubscribe():
            self.unsubscribe(pattern, handler)

        return unsubscribe

    def unsubscribe(self, pattern: str, handler: Callable[[Event], None]) -> bool:
        """
        Unsubscribe a specific handler from a pattern.

        Args:
            pattern: The subscription pattern
            handler: The handler to remove

        Returns:
            True if handler was found and removed, False otherwise
        """
        with self._lock:
            if pattern not in self._subscribers:
                return False

            try:
                self._subscribers[pattern].remove(handler)
                if not self._subscribers[pattern]:
                    del self._subscribers[pattern]
                return True
            except ValueError:
                return False

    def publish(self, event_name: str, data: Any = None) -> int:
        """
        Publish an event to all matching subscribers.

        Args:
            event_name: Name of the event to publish
            data: Optional data to attach to the event

        Returns:
            Number of handlers that were called
        """
        event = Event(name=event_name, data=data)
        handlers_called = 0

        with self._lock:
            patterns = list(self._subscribers.keys())

        for pattern in patterns:
            if fnmatch.fnmatch(event_name, pattern):
                with self._lock:
                    handlers = list(self._subscribers.get(pattern, []))

                for handler in handlers:
                    try:
                        handler(event)
                        handlers_called += 1
                    except Exception as e:
                        self._handle_error(event, handler, e)

        return handlers_called

    def unsubscribe_all(self, pattern: str) -> int:
        """Remove all handlers for a specific pattern."""
        with self._lock:
            if pattern not in self._subscribers:
                return 0
            count = len(self._subscribers[pattern])
            del self._subscribers[pattern]
            return count

    def clear(self) -> int:
        """Remove all subscriptions."""
        with self._lock:
            total = sum(len(handlers) for handlers in self._subscribers.values())
            self._subscribers.clear()
            return total

    def subscribers(self, pattern: str = None) -> Dict[str, int]:
        """Get subscriber counts for pattern(s)."""
        with self._lock:
            if pattern is None:
                return {p: len(handlers) for p, handlers in self._subscribers.items()}
            return {pattern: len(self._subscribers.get(pattern, []))}

    def _handle_error(self, event: Event, handler: Callable, error: Exception) -> None:
        """
        Handle exceptions raised by event handlers.
        Override this method to implement custom error handling.
        """
        print(f"Error in handler {handler.__name__} for event {event.name}: {error}")


if __name__ == "__main__":
    bus = EventBus()

    print("=== Example 1: Specific Event ===")
    bus.subscribe("user.created", lambda e: print(f"✓ User created: {e.data}"))
    bus.publish("user.created", {"id": 1, "name": "Alice"})

    print("\n=== Example 2: Wildcard Subscription ===")
    bus.subscribe("user.*", lambda e: print(f"✓ User event: {e.name}"))
    bus.publish("user.deleted", {"id": 1})
    bus.publish("user.updated", {"id": 1, "name": "Bob"})

    print("\n=== Example 3: Unsubscribe ===")
    unsub = bus.subscribe("test.event", lambda e: print("This won't print"))
    bus.publish("test.event")
    unsub()
    bus.publish("test.event")

    print("\n=== Example 4: Multiple Handlers ===")
    bus.subscribe("order.placed", lambda e: print(f"  1. Order {e.data['id']} placed"))
    bus.subscribe("order.placed", lambda e: print(f"  2. Send confirmation"))
    bus.subscribe("order.*", lambda e: print(f"  3. Log to analytics"))
    count = bus.publish("order.placed", {"id": 42, "total": 99.99})
    print(f"Triggered {count} handlers")

def _handle_error(self, event, handler, error):
    import logging
    logging.exception(f"Handler {handler.__name__} failed for {event.name}")

def _handle_error(self, event, handler, error):
    raise error  # Stops remaining handlers

def __init__(self, error_handler=None):
    self.error_handler = error_handler or self._default_error_handler

bus = EventBus(error_handler=my_custom_error_logic)