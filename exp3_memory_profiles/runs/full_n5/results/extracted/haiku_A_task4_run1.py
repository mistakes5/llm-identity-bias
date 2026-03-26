"""
Publish-Subscribe Event System with Wildcard Support

Architecture:
- Thread-safe subscription registry using UUID-based handler IDs
- Wildcard patterns matched using fnmatch (Unix shell-style)
- Callbacks stored with metadata for flexible unsubscription
- Support for multiple handlers per event
"""

from typing import Callable, Any, Dict, List, Set, Optional
from dataclasses import dataclass, field
from uuid import uuid4
import fnmatch
from threading import RLock
from collections import defaultdict


@dataclass
class Subscription:
    """Represents a single subscription with metadata for cleanup."""
    handler_id: str
    event_pattern: str
    callback: Callable[[str, Any], None]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def matches(self, event_name: str) -> bool:
        """Check if this subscription matches a published event."""
        return fnmatch.fnmatch(event_name, self.event_pattern)


class EventBus:
    """
    Thread-safe publish-subscribe event system.

    Features:
    - Wildcard subscriptions ("user.*", "*.created")
    - Multiple handlers per event
    - Unsubscribe by handler ID
    - Exception isolation (handler failure doesn't crash bus)
    """

    def __init__(self):
        self._subscriptions: Dict[str, List[Subscription]] = defaultdict(list)
        self._all_patterns: Set[str] = set()  # Unique patterns for efficient matching
        self._lock = RLock()
        self._handler_count = 0

    def subscribe(
        self,
        event_pattern: str,
        callback: Callable[[str, Any], None],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Subscribe to events matching a pattern.

        Args:
            event_pattern: Event name or wildcard pattern (e.g., "user.created", "user.*")
            callback: Function called with (event_name, data)
            metadata: Optional metadata for tracking subscriptions

        Returns:
            Unique handler ID for later unsubscription
        """
        handler_id = str(uuid4())
        subscription = Subscription(
            handler_id=handler_id,
            event_pattern=event_pattern,
            callback=callback,
            metadata=metadata or {},
        )

        with self._lock:
            self._subscriptions[event_pattern].append(subscription)
            self._all_patterns.add(event_pattern)
            self._handler_count += 1

        return handler_id

    def publish(self, event_name: str, data: Any = None) -> int:
        """
        Publish an event, triggering all matching subscriptions.

        Args:
            event_name: Name of the event being published
            data: Data to pass to subscribers (any type)

        Returns:
            Number of handlers called successfully
        """
        matching_handlers = self._find_matching_handlers(event_name)
        successful_calls = 0

        for subscription in matching_handlers:
            try:
                subscription.callback(event_name, data)
                successful_calls += 1
            except Exception as e:
                # Isolate handler failures: log and continue
                print(f"Error in handler for '{event_name}': {e}")

        return successful_calls

    def unsubscribe(self, handler_id: str) -> bool:
        """
        Unsubscribe a handler by ID.

        Returns:
            True if handler was found and removed, False otherwise
        """
        with self._lock:
            for pattern, subscriptions in self._subscriptions.items():
                for i, sub in enumerate(subscriptions):
                    if sub.handler_id == handler_id:
                        subscriptions.pop(i)
                        if not subscriptions:  # Clean up empty lists
                            del self._subscriptions[pattern]
                            self._all_patterns.discard(pattern)
                        self._handler_count -= 1
                        return True
        return False

    def unsubscribe_all(self, event_pattern: str) -> int:
        """Unsubscribe all handlers from a specific pattern."""
        with self._lock:
            if event_pattern not in self._subscriptions:
                return 0

            count = len(self._subscriptions[event_pattern])
            self._handler_count -= count
            del self._subscriptions[event_pattern]
            self._all_patterns.discard(event_pattern)
            return count

    def _find_matching_handlers(self, event_name: str) -> List[Subscription]:
        """Find all subscriptions matching an event name."""
        with self._lock:
            matching = []
            for pattern in self._all_patterns:
                if fnmatch.fnmatch(event_name, pattern):
                    matching.extend(self._subscriptions[pattern])
        return matching

    def get_subscription_count(self) -> int:
        """Get total number of active subscriptions."""
        with self._lock:
            return self._handler_count

    def get_pattern_count(self) -> int:
        """Get number of unique subscription patterns."""
        with self._lock:
            return len(self._all_patterns)

    def inspect(self) -> Dict[str, List[Dict[str, Any]]]:
        """Return a readable snapshot of all subscriptions."""
        with self._lock:
            return {
                pattern: [
                    {
                        "handler_id": sub.handler_id,
                        "callback": sub.callback.__name__,
                        "metadata": sub.metadata,
                    }
                    for sub in subs
                ]
                for pattern, subs in self._subscriptions.items()
            }


# Example Usage
if __name__ == "__main__":
    bus = EventBus()

    # Subscribe to all user events
    def on_user_event(event: str, data: Any):
        print(f"[USER EVENT] {event}: {data}")

    handler1 = bus.subscribe("user.*", on_user_event)
    handler2 = bus.subscribe("*.created", lambda e, d: print(f"[CREATED] {e}: {d}"))

    # Publish events
    bus.publish("user.created", {"id": 1, "name": "Alice"})
    bus.publish("user.updated", {"id": 1, "email": "alice@example.com"})
    bus.publish("product.created", {"sku": "P001"})

    # Unsubscribe
    bus.unsubscribe(handler1)
    bus.publish("user.deleted", {"id": 1})  # Won't trigger handler1

    # Inspect state
    print(f"Total subscriptions: {bus.get_subscription_count()}")
    print(f"Total patterns: {bus.get_pattern_count()}")