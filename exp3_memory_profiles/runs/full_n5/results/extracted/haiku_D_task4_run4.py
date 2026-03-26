"""
Publish-Subscribe Event System with wildcard support.

Key features:
- Pattern matching: "user.created", "user.*", "*"
- Thread-safe operations (RLock for nested publishes)
- Safe unsubscribe-during-callback
- Exception isolation between handlers
"""

import threading
from typing import Callable, Any, Dict, List
from dataclasses import dataclass


@dataclass
class Event:
    """Event payload."""
    name: str
    data: Any = None


class EventBus:
    """Thread-safe pub-sub with wildcard patterns."""

    def __init__(self):
        self._subscriptions: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()

    def subscribe(self, event_pattern: str, handler: Callable) -> int:
        """Subscribe to events matching pattern.
        
        Patterns:
            "user.created" → exact match
            "user.*" → matches "user.created", "user.deleted", etc.
            "*" → matches all events
        """
        if not isinstance(event_pattern, str) or not event_pattern:
            raise ValueError("event_pattern must be non-empty string")
        if not callable(handler):
            raise ValueError("handler must be callable")

        with self._lock:
            if event_pattern not in self._subscriptions:
                self._subscriptions[event_pattern] = []
            self._subscriptions[event_pattern].append(handler)
            return id(handler)

    def unsubscribe(self, event_pattern: str, handler: Callable) -> bool:
        """Remove handler from pattern. Safe during callbacks."""
        with self._lock:
            if event_pattern not in self._subscriptions:
                return False
            try:
                self._subscriptions[event_pattern].remove(handler)
                if not self._subscriptions[event_pattern]:
                    del self._subscriptions[event_pattern]
                return True
            except ValueError:
                return False

    def publish(self, event_name: str, data: Any = None) -> None:
        """Publish event to all matching subscribers.
        
        Exceptions in handlers don't stop other handlers.
        Subscribers are called synchronously in subscription order.
        """
        event = Event(name=event_name, data=data)

        with self._lock:
            matching_handlers = self._get_matching_handlers(event_name)

        # Execute outside lock to allow nested publishes/unsubscribes
        for handler in matching_handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"Error in handler for {event_name}: {e}")

    def _get_matching_handlers(self, event_name: str) -> List[Callable]:
        """Find all handlers matching event name. Must hold lock."""
        handlers = []
        for pattern, pattern_handlers in self._subscriptions.items():
            if self._matches_pattern(event_name, pattern):
                handlers.extend(pattern_handlers[:])  # Copy to avoid iterator issues
        return handlers

    @staticmethod
    def _matches_pattern(event_name: str, pattern: str) -> bool:
        """Check if event_name matches subscription pattern."""
        if pattern == event_name:
            return True
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            return event_name.startswith(prefix + ".")
        if pattern == "*":
            return True
        return False

    def list_subscriptions(self) -> Dict[str, int]:
        """Get subscriber counts per pattern for debugging."""
        with self._lock:
            return {p: len(h) for p, h in self._subscriptions.items()}

    def clear(self) -> None:
        """Remove all subscriptions."""
        with self._lock:
            self._subscriptions.clear()


# Example usage
if __name__ == "__main__":
    bus = EventBus()
    
    def on_user_created(event: Event):
        print(f"[EXACT] User created: {event.data}")
    
    def on_user_event(event: Event):
        print(f"[WILDCARD] {event.name}: {event.data}")
    
    def on_any_event(event: Event):
        print(f"[CATCH-ALL] {event.name}")
    
    # Subscribe
    bus.subscribe("user.created", on_user_created)
    bus.subscribe("user.*", on_user_event)
    bus.subscribe("*", on_any_event)
    
    # Publish
    bus.publish("user.created", {"id": 1, "email": "alice@example.com"})
    bus.publish("user.deleted", {"id": 1})
    bus.publish("payment.processed", {"amount": 99.99})
    
    # Unsubscribe
    bus.unsubscribe("user.*", on_user_event)
    bus.publish("user.updated", {"id": 1, "name": "Alice"})

def self_destructing_handler(event: Event):
    print(f"Fired once: {event}")
    bus.unsubscribe("user.*", self_destructing_handler)

bus.subscribe("user.*", self_destructing_handler)

bus.subscribe("order.created.pending", handler1)
bus.subscribe("order.created.*", handler2)      # Matches pending, shipped, etc.
bus.subscribe("order.*", handler3)               # Matches all order events
bus.subscribe("*", handler4)                     # Matches everything

async def async_handler(event: Event):
    await do_something()

# Wrap in sync adapter
def sync_wrapper(event: Event):
    import asyncio
    asyncio.create_task(async_handler(event))

bus.subscribe("order.created", sync_wrapper)