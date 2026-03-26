"""
Publish-Subscribe Event System

A flexible event bus supporting:
- Direct event subscriptions
- Wildcard subscriptions (e.g., "user.*" matches "user.created", "user.deleted")
- Multiple subscribers per event
- Thread-safe operations
"""

from collections import defaultdict
from typing import Callable, Any, Optional, Tuple
from threading import RLock
from fnmatch import fnmatch
import uuid


class EventBus:
    """A thread-safe pub-sub event system with wildcard support."""

    def __init__(self):
        """Initialize the event bus."""
        self._subscribers: dict[str, list[Tuple[str, Callable]]] = defaultdict(list)
        self._lock = RLock()

    def subscribe(self, event: str, callback: Callable[[Any], None]) -> str:
        """
        Subscribe to an event or event pattern.

        Args:
            event: Event name or wildcard pattern (e.g., "user.created" or "user.*")
            callback: Callable that receives event data

        Returns:
            Subscription ID for later unsubscribe
        """
        if not callable(callback):
            raise TypeError("callback must be callable")

        subscription_id = str(uuid.uuid4())

        with self._lock:
            self._subscribers[event].append((subscription_id, callback))

        return subscription_id

    def unsubscribe(self, event: str, subscription_id: str) -> bool:
        """
        Unsubscribe from an event.

        Args:
            event: Event name or pattern to unsubscribe from
            subscription_id: ID returned by subscribe()

        Returns:
            True if unsubscribe was successful, False if not found
        """
        with self._lock:
            if event not in self._subscribers:
                return False

            original_count = len(self._subscribers[event])
            self._subscribers[event] = [
                (sub_id, callback)
                for sub_id, callback in self._subscribers[event]
                if sub_id != subscription_id
            ]

            # Clean up empty entries
            if not self._subscribers[event]:
                del self._subscribers[event]

            return len(self._subscribers[event]) < original_count

    def unsubscribe_all(self, event: Optional[str] = None) -> int:
        """
        Unsubscribe all listeners from an event, or all events.

        Args:
            event: Specific event to clear, or None to clear all

        Returns:
            Number of subscriptions removed
        """
        with self._lock:
            if event is None:
                count = sum(len(subs) for subs in self._subscribers.values())
                self._subscribers.clear()
                return count

            count = len(self._subscribers.get(event, []))
            if event in self._subscribers:
                del self._subscribers[event]
            return count

    def publish(self, event: str, data: Any = None) -> int:
        """
        Publish an event to all matching subscribers.

        Subscribers are matched in two ways:
        1. Exact match: "user.created" subscribers get the event
        2. Wildcard match: "user.*" or "*" subscribers get the event

        Args:
            event: Event name to publish
            data: Data to pass to subscribers (can be any type)

        Returns:
            Number of subscribers called
        """
        with self._lock:
            subscribers_to_call = []

            # Find exact matches and wildcard matches
            for pattern, subs in self._subscribers.items():
                if self._matches(pattern, event):
                    subscribers_to_call.extend(subs)

        # Call subscribers outside the lock to prevent deadlocks
        for subscription_id, callback in subscribers_to_call:
            try:
                callback(data)
            except Exception as e:
                # Log but don't stop other callbacks
                print(f"Error in callback for event '{event}': {e}")

        return len(subscribers_to_call)

    def _matches(self, pattern: str, event: str) -> bool:
        """Check if an event matches a subscription pattern."""
        # fnmatch handles wildcard patterns like "user.*", "*.created", "*"
        return fnmatch(event, pattern)

    def get_subscribers(self, event: Optional[str] = None) -> dict[str, int]:
        """
        Get count of subscribers by event pattern.

        Args:
            event: Specific event to check, or None for all

        Returns:
            Dict mapping event patterns to subscriber counts
        """
        with self._lock:
            if event is None:
                return {e: len(subs) for e, subs in self._subscribers.items()}
            return {event: len(self._subscribers.get(event, []))}

# Create an event bus
bus = EventBus()

# Subscribe to specific events
user_created_id = bus.subscribe("user.created", lambda data: print(f"New user: {data['name']}"))
user_deleted_id = bus.subscribe("user.deleted", lambda data: print(f"User deleted: {data['id']}"))

# Subscribe to wildcard patterns
bus.subscribe("user.*", lambda data: print(f"User event occurred: {data}"))
bus.subscribe("*", lambda data: print(f"[GLOBAL] Any event: {data}"))

# Publish events
bus.publish("user.created", {"id": 1, "name": "Alice"})
bus.publish("user.deleted", {"id": 2})
bus.publish("post.created", {"id": 100, "title": "Hello World"})

# Unsubscribe
bus.unsubscribe("user.created", user_created_id)

# Get subscriber info
print(bus.get_subscribers())  # {"user.deleted": 1, "user.*": 1, "*": 1}

# Clear all subscribers for an event
bus.unsubscribe_all("user.*")

# Clear everything
bus.unsubscribe_all()