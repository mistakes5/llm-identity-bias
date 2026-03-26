from typing import Callable, Any, Dict, List
from dataclasses import dataclass
import threading


@dataclass
class Event:
    """Represents a publishable event with metadata."""
    topic: str
    data: Dict[str, Any]

    def __repr__(self) -> str:
        return f"Event(topic='{self.topic}', data={self.data})"


class PubSub:
    """Thread-safe publish-subscribe event broker with wildcard support."""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._pattern_subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()

    def subscribe(self, topic: str, callback: Callable[[Event], None]) -> Callable:
        """Subscribe to events on a topic or pattern. Returns unsubscribe function."""
        with self._lock:
            if '*' in topic:
                if topic not in self._pattern_subscribers:
                    self._pattern_subscribers[topic] = []
                self._pattern_subscribers[topic].append(callback)
            else:
                if topic not in self._subscribers:
                    self._subscribers[topic] = []
                self._subscribers[topic].append(callback)
        
        return lambda: self.unsubscribe(topic, callback)

    def unsubscribe(self, topic: str, callback: Callable) -> bool:
        """Unsubscribe a callback from a topic or pattern."""
        with self._lock:
            if '*' in topic:
                subscribers = self._pattern_subscribers.get(topic, [])
            else:
                subscribers = self._subscribers.get(topic, [])
            
            if callback in subscribers:
                subscribers.remove(callback)
                return True
            return False

    def publish(self, topic: str, data: Dict[str, Any] | None = None) -> int:
        """Publish an event to all matching subscribers."""
        event = Event(topic=topic, data=data or {})
        callback_count = 0

        with self._lock:
            callbacks_to_invoke = []
            
            # Direct topic matches
            for callback in self._subscribers.get(topic, []):
                callbacks_to_invoke.append(callback)
            
            # Pattern matches
            for pattern, callbacks in self._pattern_subscribers.items():
                if self._matches_pattern(topic, pattern):
                    for callback in callbacks:
                        callbacks_to_invoke.append(callback)

        # Invoke callbacks outside the lock
        for callback in callbacks_to_invoke:
            try:
                callback(event)
            except Exception as e:
                print(f"Error invoking callback {callback.__name__}: {e}")
            callback_count += 1

        return callback_count

    def _matches_pattern(self, topic: str, pattern: str) -> bool:
        """
        Check if a topic matches a wildcard pattern.
        
        'user.*' matches 'user.created', 'user.deleted'
        '*.created' matches 'user.created', 'order.created'
        
        Implement this method!
        """
        raise NotImplementedError()

    def subscribers(self, topic: str | None = None) -> Dict[str, int]:
        """Get subscriber counts for debugging."""
        with self._lock:
            if topic:
                count = len(self._subscribers.get(topic, []))
                count += len(self._pattern_subscribers.get(topic, []))
                return {topic: count}

            result = {}
            for t, callbacks in self._subscribers.items():
                result[t] = len(callbacks)
            for t, callbacks in self._pattern_subscribers.items():
                result[f"{t} (pattern)"] = len(callbacks)
            return result

if __name__ == "__main__":
    pubsub = PubSub()

    def on_user_event(event: Event):
        print(f"  → {event.topic}")

    def on_created_event(event: Event):
        print(f"  ✓ {event.topic}")

    # Subscribe
    pubsub.subscribe("user.*", on_user_event)
    pubsub.subscribe("*.created", on_created_event)

    # Test cases
    tests = [
        ("user.created", ["user.*", "*.created"]),      # Both match
        ("user.deleted", ["user.*"]),                    # Only user.*
        ("order.created", ["*.created"]),                # Only *.created
        ("user.account.verified", []),                   # No matches
    ]

    for topic, expected_patterns in tests:
        print(f"\nPublishing: {topic}")
        count = pubsub.publish(topic, {})
        print(f"  Callbacks invoked: {count}, Expected pattern matches: {expected_patterns}")