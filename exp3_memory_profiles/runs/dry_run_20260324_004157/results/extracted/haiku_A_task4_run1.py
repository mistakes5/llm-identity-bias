"""
Publish-Subscribe Event System

A flexible, thread-safe event system supporting:
- Exact event subscriptions
- Wildcard pattern subscriptions (e.g., "user.*")
- Event publishing with arbitrary data
- Multiple subscribers per event
"""

from typing import Callable, Any, Dict, List
from dataclasses import dataclass
from threading import RLock
from fnmatch import fnmatch


@dataclass
class Event:
    """Represents an event with name and data."""
    name: str
    data: Any = None


class EventBus:
    """
    Central event bus for publish-subscribe communication.

    Supports exact subscriptions and wildcard patterns.
    Thread-safe for concurrent operations.
    """

    def __init__(self):
        self._exact_subscribers: Dict[str, List[Callable]] = {}
        self._pattern_subscribers: Dict[str, List[Callable]] = {}
        self._lock = RLock()
        self._subscription_ids: Dict[int, tuple] = {}

    def subscribe(self, event_pattern: str, callback: Callable) -> int:
        """
        Subscribe to an event or event pattern.

        Args:
            event_pattern: Event name or wildcard pattern (e.g., "user.*")
            callback: Function to call when event is published.
                     Receives Event object as argument.

        Returns:
            Subscription ID for later unsubscription.
        """
        with self._lock:
            is_pattern = "*" in event_pattern or "#" in event_pattern

            if is_pattern:
                if event_pattern not in self._pattern_subscribers:
                    self._pattern_subscribers[event_pattern] = []
                self._pattern_subscribers[event_pattern].append(callback)
            else:
                if event_pattern not in self._exact_subscribers:
                    self._exact_subscribers[event_pattern] = []
                self._exact_subscribers[event_pattern].append(callback)

            sub_id = id(callback) ^ hash(event_pattern)
            self._subscription_ids[sub_id] = (event_pattern, callback, is_pattern)
            return sub_id

    def unsubscribe(self, subscription_id: int) -> bool:
        """
        Unsubscribe using the subscription ID returned by subscribe().

        Returns:
            True if unsubscribed successfully, False if ID not found.
        """
        with self._lock:
            if subscription_id not in self._subscription_ids:
                return False

            event_pattern, callback, is_pattern = self._subscription_ids[subscription_id]
            subscribers = (
                self._pattern_subscribers if is_pattern
                else self._exact_subscribers
            ).get(event_pattern, [])

            try:
                subscribers.remove(callback)
                del self._subscription_ids[subscription_id]
                return True
            except ValueError:
                return False

    def publish(self, event_name: str, data: Any = None) -> int:
        """
        Publish an event to all matching subscribers.

        Returns:
            Number of subscribers notified.
        """
        event = Event(name=event_name, data=data)
        notified = 0

        with self._lock:
            # Notify exact subscribers
            for callback in self._exact_subscribers.get(event_name, []):
                try:
                    callback(event)
                    notified += 1
                except Exception as e:
                    print(f"Error in callback for '{event_name}': {e}")

            # Notify pattern subscribers
            for pattern, callbacks in self._pattern_subscribers.items():
                if fnmatch(event_name, pattern):
                    for callback in callbacks:
                        try:
                            callback(event)
                            notified += 1
                        except Exception as e:
                            print(f"Error in callback for pattern '{pattern}': {e}")

        return notified

    def get_subscriber_count(self, event_pattern: str = None) -> int:
        """Get count of subscribers."""
        with self._lock:
            if event_pattern is None:
                total = sum(len(subs) for subs in self._exact_subscribers.values())
                total += sum(len(subs) for subs in self._pattern_subscribers.values())
                return total

            is_pattern = "*" in event_pattern or "#" in event_pattern
            if is_pattern:
                return len(self._pattern_subscribers.get(event_pattern, []))
            else:
                return len(self._exact_subscribers.get(event_pattern, []))

    def clear(self):
        """Remove all subscribers and subscriptions."""
        with self._lock:
            self._exact_subscribers.clear()
            self._pattern_subscribers.clear()
            self._subscription_ids.clear()

import pytest
from collections import defaultdict
import time
from threading import Thread


class TestEventBus:
    """Test the EventBus implementation."""

    def setup_method(self):
        """Create a fresh EventBus for each test."""
        self.bus = EventBus()
        self.events_received = []

    def handler(self, event):
        """Capture received events."""
        self.events_received.append(event)

    # ── Basic Subscription & Publishing ──

    def test_subscribe_and_publish_exact_match(self):
        """Test basic subscription and event publishing."""
        self.bus.subscribe("user.login", self.handler)
        notified = self.bus.publish("user.login", {"user_id": 123})

        assert notified == 1
        assert len(self.events_received) == 1
        assert self.events_received[0].name == "user.login"
        assert self.events_received[0].data == {"user_id": 123}

    def test_publish_without_subscribers(self):
        """Publishing to non-subscribed events returns 0."""
        notified = self.bus.publish("no.subscribers", {"data": "test"})
        assert notified == 0
        assert len(self.events_received) == 0

    def test_multiple_subscribers_exact_match(self):
        """Multiple subscribers for same event all receive it."""
        def handler2(event):
            self.events_received.append(f"handler2: {event.name}")

        self.bus.subscribe("user.login", self.handler)
        self.bus.subscribe("user.login", handler2)

        notified = self.bus.publish("user.login", {})
        assert notified == 2

    # ── Wildcard Subscriptions ──

    def test_wildcard_subscription_asterisk(self):
        """Wildcard with * matches multiple events."""
        self.bus.subscribe("user.*", self.handler)

        self.bus.publish("user.login", {"action": "login"})
        self.bus.publish("user.logout", {"action": "logout"})
        self.bus.publish("user.profile.update", {"action": "update"})

        assert len(self.events_received) == 3
        names = [e.name for e in self.events_received]
        assert set(names) == {"user.login", "user.logout", "user.profile.update"}

    def test_wildcard_does_not_match_prefix(self):
        """Wildcard only matches within the pattern scope."""
        self.bus.subscribe("user.*", self.handler)

        self.bus.publish("user", {})  # No match
        self.bus.publish("user.login", {})  # Match
        self.bus.publish("user_login", {})  # No match
        self.bus.publish("admin.user.login", {})  # No match

        assert len(self.events_received) == 1
        assert self.events_received[0].name == "user.login"

    def test_wildcard_subscription_hash(self):
        """Wildcard with # (alternative pattern)."""
        self.bus.subscribe("error.#", self.handler)

        self.bus.publish("error.database", {})
        self.bus.publish("error.network", {})
        self.bus.publish("warning.database", {})  # No match

        assert len(self.events_received) == 2

    def test_multiple_matching_patterns(self):
        """Multiple wildcard patterns can match same event."""
        def handler2(event):
            self.events_received.append(f"handler2: {event.name}")

        self.bus.subscribe("user.*", self.handler)
        self.bus.subscribe("*.login", handler2)

        notified = self.bus.publish("user.login", {})
        assert notified == 2
        assert len(self.events_received) == 2

    # ── Unsubscription ──

    def test_unsubscribe_by_id(self):
        """Can unsubscribe using returned subscription ID."""
        sub_id = self.bus.subscribe("user.login", self.handler)
        assert self.bus.unsubscribe(sub_id) is True

        self.bus.publish("user.login", {})
        assert len(self.events_received) == 0

    def test_unsubscribe_invalid_id(self):
        """Unsubscribing with invalid ID returns False."""
        assert self.bus.unsubscribe(99999) is False

    def test_unsubscribe_only_target_callback(self):
        """Unsubscribing one callback doesn't affect others."""
        def handler2(event):
            self.events_received.append(f"handler2")

        sub_id1 = self.bus.subscribe("user.login", self.handler)
        sub_id2 = self.bus.subscribe("user.login", handler2)

        self.bus.unsubscribe(sub_id1)

        notified = self.bus.publish("user.login", {})
        assert notified == 1
        assert "handler2" in self.events_received[0]

    def test_unsubscribe_twice_fails(self):
        """Cannot unsubscribe the same ID twice."""
        sub_id = self.bus.subscribe("user.login", self.handler)
        assert self.bus.unsubscribe(sub_id) is True
        assert self.bus.unsubscribe(sub_id) is False

    # ── Event Data ──

    def test_event_data_passed_correctly(self):
        """Event data is passed to subscriber."""
        data = {"user_id": 42, "name": "Alice", "roles": ["admin", "user"]}
        self.bus.subscribe("user.created", self.handler)

        self.bus.publish("user.created", data)

        assert self.events_received[0].data == data
        assert self.events_received[0].data["user_id"] == 42

    def test_event_with_none_data(self):
        """Event can be published without data."""
        self.bus.subscribe("ping", self.handler)

        self.bus.publish("ping")

        assert self.events_received[0].data is None

    # ── Subscriber Count ──

    def test_get_subscriber_count_all(self):
        """Count all subscribers across all patterns."""
        self.bus.subscribe("user.login", self.handler)
        self.bus.subscribe("user.*", self.handler)
        self.bus.subscribe("order.created", self.handler)

        assert self.bus.get_subscriber_count() == 3

    def test_get_subscriber_count_specific_pattern(self):
        """Count subscribers for specific pattern."""
        def handler2(event):
            pass

        self.bus.subscribe("user.login", self.handler)
        self.bus.subscribe("user.login", handler2)
        self.bus.subscribe("order.created", self.handler)

        assert self.bus.get_subscriber_count("user.login") == 2
        assert self.bus.get_subscriber_count("order.created") == 1
        assert self.bus.get_subscriber_count("user.*") == 0

    # ── Error Handling ──

    def test_callback_exception_doesnt_break_others(self):
        """Exception in one callback doesn't stop others."""
        def bad_handler(event):
            raise ValueError("Handler error")

        def good_handler(event):
            self.events_received.append("success")

        self.bus.subscribe("test.event", bad_handler)
        self.bus.subscribe("test.event", good_handler)

        notified = self.bus.publish("test.event", {})

        assert notified == 2
        assert "success" in self.events_received

    # ── Clear ──

    def test_clear_removes_all_subscribers(self):
        """Clear removes all subscriptions."""
        self.bus.subscribe("user.login", self.handler)
        self.bus.subscribe("user.*", self.handler)
        self.bus.subscribe("order.*", self.handler)

        assert self.bus.get_subscriber_count() == 3

        self.bus.clear()

        assert self.bus.get_subscriber_count() == 0
        notified = self.bus.publish("user.login", {})
        assert notified == 0

    # ── Thread Safety ──

    def test_thread_safe_concurrent_subscriptions(self):
        """Concurrent subscriptions and publishes work correctly."""
        results = defaultdict(int)

        def make_handler(name):
            def h(event):
                results[name] += 1
            return h

        def subscriber_thread():
            for i in range(100):
                self.bus.subscribe(f"event.{i % 10}", make_handler(f"sub_{i}"))

        threads = [Thread(target=subscriber_thread) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify no crashes and subscriptions succeeded
        assert self.bus.get_subscriber_count() > 0

    # ── Real-World Scenarios ──

    def test_user_activity_tracking(self):
        """Real-world: track user activities with wildcards."""
        activities = []

        def track_activity(event):
            activities.append({
                "action": event.name.split(".")[-1],
                "user_id": event.data.get("user_id")
            })

        self.bus.subscribe("user.*", track_activity)

        self.bus.publish("user.login", {"user_id": 1})
        self.bus.publish("user.logout", {"user_id": 1})
        self.bus.publish("user.profile.update", {"user_id": 1})

        assert len(activities) == 3
        assert activities[0]["action"] == "login"

    def test_error_severity_levels(self):
        """Real-world: subscribe to error levels."""
        errors = {"critical": [], "warning": []}

        def critical_handler(event):
            errors["critical"].append(event.data)

        def warning_handler(event):
            errors["warning"].append(event.data)

        self.bus.subscribe("error.critical.*", critical_handler)
        self.bus.subscribe("error.warning.*", warning_handler)

        self.bus.publish("error.critical.database", {"msg": "Connection lost"})
        self.bus.publish("error.warning.memory", {"msg": "Usage high"})
        self.bus.publish("error.critical.auth", {"msg": "Invalid token"})

        assert len(errors["critical"]) == 2
        assert len(errors["warning"]) == 1


# ── Run Tests ──
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

# Create a bus
bus = EventBus()

# Subscribe to exact events
sub_id = bus.subscribe("user.login", lambda e: print(f"User {e.data['id']} logged in"))

# Subscribe to patterns
bus.subscribe("user.*", lambda e: print(f"User event: {e.name}"))
bus.subscribe("error.*", lambda e: print(f"⚠ Error: {e.data}"))

# Publish events
bus.publish("user.login", {"id": 123, "name": "Alice"})
bus.publish("error.database", {"code": 500})

# Unsubscribe
bus.unsubscribe(sub_id)

# Query subscribers
count = bus.get_subscriber_count()  # Total
count = bus.get_subscriber_count("user.login")  # Specific pattern