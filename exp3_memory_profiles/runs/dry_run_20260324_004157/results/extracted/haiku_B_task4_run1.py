"""Publish-Subscribe Event System with Wildcard Support"""

from typing import Callable, Any, Dict, List, Tuple
import fnmatch
import threading
from dataclasses import dataclass
from uuid import uuid4


@dataclass
class Event:
    """Represents an event with name and associated data."""
    name: str
    data: Any = None


class EventBus:
    """Thread-safe pub-sub event bus with wildcard pattern matching."""

    def __init__(self):
        self._subscriptions: Dict[str, List[Tuple[str, Callable]]] = {}
        self._lock = threading.RLock()

    def subscribe(self, event_pattern: str, callback: Callable[[Event], None]) -> str:
        """
        Subscribe to an event pattern.
        
        Args:
            event_pattern: Event name or wildcard (e.g., "user.*", "*.created")
            callback: Function accepting Event object
        
        Returns:
            Subscription ID for later unsubscription
        """
        subscription_id = str(uuid4())

        with self._lock:
            if event_pattern not in self._subscriptions:
                self._subscriptions[event_pattern] = []
            self._subscriptions[event_pattern].append((subscription_id, callback))

        return subscription_id

    def unsubscribe(self, event_pattern: str, subscription_id: str) -> bool:
        """Remove a subscription by pattern and ID."""
        with self._lock:
            if event_pattern not in self._subscriptions:
                return False

            subscriptions = self._subscriptions[event_pattern]
            original_length = len(subscriptions)

            self._subscriptions[event_pattern] = [
                (sub_id, cb) for sub_id, cb in subscriptions
                if sub_id != subscription_id
            ]

            if not self._subscriptions[event_pattern]:
                del self._subscriptions[event_pattern]

            return original_length > len(self._subscriptions.get(event_pattern, []))

    def publish(self, event_name: str, data: Any = None) -> None:
        """Publish an event, triggering all matching subscriptions."""
        event = Event(name=event_name, data=data)

        with self._lock:
            matching_callbacks = []
            for pattern, subscriptions in self._subscriptions.items():
                if self._matches_pattern(event_name, pattern):
                    matching_callbacks.extend(subscriptions)

        # Execute callbacks outside the lock
        for subscription_id, callback in matching_callbacks:
            try:
                callback(event)
            except Exception as e:
                print(f"Callback error: {e}")

    @staticmethod
    def _matches_pattern(event_name: str, pattern: str) -> bool:
        """Match event name against wildcard pattern using fnmatch."""
        return fnmatch.fnmatch(event_name, pattern)

    def get_subscription_count(self, pattern: str = None) -> int:
        """Get subscription count for a pattern or total."""
        with self._lock:
            if pattern:
                return len(self._subscriptions.get(pattern, []))
            return sum(len(subs) for subs in self._subscriptions.values())

# Initialize
bus = EventBus()

# 1. Exact subscriptions
sub1 = bus.subscribe("user.created", lambda e: print(f"User: {e.data}"))

# 2. Wildcard subscriptions  
sub2 = bus.subscribe("user.*", lambda e: print(f"User event: {e.name}"))
sub3 = bus.subscribe("*.created", lambda e: print(f"Created: {e.name}"))

# 3. Publish events
bus.publish("user.created", {"id": 1, "name": "Alice"})
# Output:
#   User: {'id': 1, 'name': 'Alice'}
#   User event: user.created
#   Created: user.created

# 4. Unsubscribe
bus.unsubscribe("user.created", sub1)

# 5. Query subscriptions
print(bus.get_subscription_count())  # Total subscriptions
print(bus.get_subscription_count("user.*"))  # Count for specific pattern

def test_event_bus():
    bus = EventBus()
    results = []
    
    # Test exact matching
    bus.subscribe("order.shipped", lambda e: results.append(("exact", e.data)))
    bus.publish("order.shipped", {"id": 1})
    assert results[-1] == ("exact", {"id": 1}), "Exact match failed"
    
    # Test wildcard patterns
    bus.subscribe("order.*", lambda e: results.append(("wildcard_order", e.name)))
    bus.subscribe("*.paid", lambda e: results.append(("wildcard_paid", e.name)))
    
    bus.publish("order.paid", {"amount": 99.99})
    # Should match: "order.*" and "*.paid"
    assert ("wildcard_order", "order.paid") in results
    assert ("wildcard_paid", "order.paid") in results
    
    # Test unsubscribe
    sub = bus.subscribe("user.created", lambda e: results.append("should_not_appear"))
    bus.unsubscribe("user.created", sub)
    bus.publish("user.created", {})
    assert "should_not_appear" not in results
    
    # Test error handling
    def failing_callback(e):
        raise ValueError("Intentional error")
    
    bus.subscribe("test.error", failing_callback)
    bus.subscribe("test.error", lambda e: results.append("should_still_run"))
    bus.publish("test.error", {})  # One callback fails, but others run
    assert "should_still_run" in results
    
    print("All tests passed!")

test_event_bus()