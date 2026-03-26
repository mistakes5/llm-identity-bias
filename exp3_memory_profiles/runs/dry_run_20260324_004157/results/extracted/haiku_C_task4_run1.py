# pubsub_event_system.py
"""
Publish-Subscribe Event System

A flexible event system supporting:
- Named event subscriptions
- Multiple subscribers per event
- Wildcard subscriptions (e.g., "user.*" matches "user.login", "user.logout")
- Subscriber management (subscribe/unsubscribe)
- Custom exception handling
"""

from typing import Callable, Any, Dict, List, Optional, Pattern
import re
from dataclasses import dataclass


@dataclass
class Event:
    """Represents a published event with metadata."""
    name: str
    data: Any = None
    source: Optional[str] = None

    def __repr__(self) -> str:
        return f"Event(name={self.name!r}, data={self.data!r})"


@dataclass
class Subscription:
    """Internal representation of a subscription."""
    event_pattern: str
    callback: Callable
    is_wildcard: bool = False
    pattern_regex: Optional[Pattern] = None


class EventBus:
    """
    A publish-subscribe event bus supporting exact matches and wildcard patterns.

    Example:
        bus = EventBus()

        def on_user_login(event):
            print(f"User logged in: {event.data}")

        # Exact subscription
        bus.subscribe("user.login", on_user_login)

        # Wildcard subscription
        bus.subscribe("user.*", lambda e: print(f"User event: {e.name}"))

        # Publish event
        bus.publish("user.login", {"username": "alice"})
    """

    def __init__(self, error_handler: Optional[Callable[[Exception, Event], None]] = None):
        """Initialize the event bus."""
        self._subscriptions: Dict[str, List[Subscription]] = {}
        self._wildcard_subscriptions: List[Subscription] = []
        self._error_handler = error_handler
        self._history: List[Event] = []
        self._max_history = 100

    def subscribe(
        self,
        event_pattern: str,
        callback: Callable[[Event], None],
        include_history: bool = False
    ) -> Callable:
        """
        Subscribe to an event pattern.

        Args:
            event_pattern: Event name or wildcard pattern (e.g., "user.login" or "user.*")
            callback: Function to call when event is published. Receives Event object.
            include_history: If True, call callback with recent matching events.

        Returns:
            Unsubscribe function for convenience.
        """
        is_wildcard = "*" in event_pattern

        if is_wildcard:
            pattern_regex = self._compile_wildcard_pattern(event_pattern)
            subscription = Subscription(
                event_pattern=event_pattern,
                callback=callback,
                is_wildcard=True,
                pattern_regex=pattern_regex
            )
            self._wildcard_subscriptions.append(subscription)
        else:
            subscription = Subscription(
                event_pattern=event_pattern,
                callback=callback,
                is_wildcard=False
            )
            if event_pattern not in self._subscriptions:
                self._subscriptions[event_pattern] = []
            self._subscriptions[event_pattern].append(subscription)

        # Call with history if requested
        if include_history:
            matching_events = [
                e for e in self._history
                if self._pattern_matches(e.name, event_pattern)
            ]
            for event in matching_events:
                self._safe_call(callback, event)

        # Return unsubscribe function
        return lambda: self.unsubscribe(event_pattern, callback)

    def unsubscribe(self, event_pattern: str, callback: Callable) -> bool:
        """
        Unsubscribe from an event pattern.

        Returns:
            True if the subscription was found and removed, False otherwise.
        """
        subscriptions_list = (
            self._wildcard_subscriptions if "*" in event_pattern
            else self._subscriptions.get(event_pattern, [])
        )

        for i, sub in enumerate(subscriptions_list):
            if sub.callback is callback:
                subscriptions_list.pop(i)
                return True

        return False

    def publish(self, event_name: str, data: Any = None, source: Optional[str] = None) -> Event:
        """
        Publish an event to all matching subscribers.

        Returns:
            The Event object that was published
        """
        event = Event(name=event_name, data=data, source=source)

        # Store in history
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        # Call exact match subscribers
        for subscription in self._subscriptions.get(event_name, []):
            self._safe_call(subscription.callback, event)

        # Call wildcard subscribers
        for subscription in self._wildcard_subscriptions:
            if subscription.pattern_regex.match(event_name):
                self._safe_call(subscription.callback, event)

        return event

    def unsubscribe_all(self, event_pattern: Optional[str] = None) -> None:
        """Clear all subscriptions for a pattern, or all if pattern is None."""
        if event_pattern is None:
            self._subscriptions.clear()
            self._wildcard_subscriptions.clear()
        elif "*" in event_pattern:
            self._wildcard_subscriptions = [
                s for s in self._wildcard_subscriptions
                if s.event_pattern != event_pattern
            ]
        else:
            self._subscriptions.pop(event_pattern, None)

    def get_subscribers(self, event_pattern: Optional[str] = None) -> Dict[str, int]:
        """Get subscription counts."""
        if event_pattern is None:
            counts = {
                pattern: len(subs)
                for pattern, subs in self._subscriptions.items()
            }
            for sub in self._wildcard_subscriptions:
                counts[sub.event_pattern] = counts.get(sub.event_pattern, 0) + 1
            return counts

        if "*" in event_pattern:
            count = sum(1 for s in self._wildcard_subscriptions if s.event_pattern == event_pattern)
        else:
            count = len(self._subscriptions.get(event_pattern, []))

        return {event_pattern: count}

    def get_history(self, event_pattern: Optional[str] = None, limit: int = 10) -> List[Event]:
        """Get recent events from history."""
        if event_pattern is None:
            return self._history[-limit:]

        matching = [
            e for e in self._history
            if self._pattern_matches(e.name, event_pattern)
        ]
        return matching[-limit:]

    # Private methods

    @staticmethod
    def _compile_wildcard_pattern(pattern: str) -> Pattern:
        """Compile a wildcard pattern (e.g., 'user.*') to regex."""
        escaped = re.escape(pattern)
        regex_pattern = escaped.replace(r"\*", ".*")
        return re.compile(f"^{regex_pattern}$")

    def _pattern_matches(self, event_name: str, pattern: str) -> bool:
        """Check if an event name matches a pattern."""
        if "*" not in pattern:
            return event_name == pattern
        regex = self._compile_wildcard_pattern(pattern)
        return regex.match(event_name) is not None

    def _safe_call(self, callback: Callable, event: Event) -> None:
        """Call a callback, handling exceptions gracefully."""
        try:
            callback(event)
        except Exception as e:
            if self._error_handler:
                self._error_handler(e, event)
            else:
                raise

# example_usage.py
from pubsub_event_system import EventBus, Event

# Create an event bus with error handling
def handle_error(exc: Exception, event: Event):
    print(f"❌ Error in subscriber for {event.name}: {exc}")

bus = EventBus(error_handler=handle_error)

# ============================================================
# 1. EXACT SUBSCRIPTIONS
# ============================================================
def on_user_login(event: Event):
    user = event.data
    print(f"✅ User '{user['name']}' logged in from {user['ip']}")

def on_user_logout(event: Event):
    user = event.data
    print(f"👋 User '{user['name']}' logged out")

bus.subscribe("user.login", on_user_login)
bus.subscribe("user.logout", on_user_logout)

# ============================================================
# 2. WILDCARD SUBSCRIPTIONS
# ============================================================
def on_any_user_event(event: Event):
    print(f"🔔 [USER EVENT] {event.name}: {event.data}")

unsub_wildcard = bus.subscribe("user.*", on_any_user_event)

# ============================================================
# 3. PUBLISH EVENTS
# ============================================================
print("\n--- Publishing Events ---\n")

bus.publish("user.login", {"name": "alice", "ip": "192.168.1.1"})
bus.publish("user.logout", {"name": "bob"})

# ============================================================
# 4. NESTED WILDCARDS
# ============================================================
def on_notification(event: Event):
    print(f"🔊 Notification: {event.data}")

bus.subscribe("notification.*.alert", on_notification)
bus.subscribe("notification.email.*", on_notification)

print("\n--- Nested Wildcard Tests ---\n")
bus.publish("notification.ui.alert", "New message!")
bus.publish("notification.email.sent", "Email delivered successfully")
bus.publish("notification.sms.received", "SMS from +1234567890")  # Won't match

# ============================================================
# 5. UNSUBSCRIBE
# ============================================================
print("\n--- Unsubscribe Test ---\n")
unsub_wildcard()  # Remove wildcard subscription
bus.publish("user.login", {"name": "charlie", "ip": "10.0.0.1"})
print("(Notice: wildcard handler didn't fire)\n")

# ============================================================
# 6. MULTIPLE SUBSCRIBERS
# ============================================================
def log_event(event: Event):
    print(f"📝 [LOG] {event.name}: {event.data}")

def audit_event(event: Event):
    print(f"🔐 [AUDIT] {event.name} at {event.source or 'unknown'}")

bus.subscribe("user.login", log_event)
bus.subscribe("user.login", audit_event)

print("--- Multiple Subscribers ---\n")
bus.publish("user.login", {"name": "diana"}, source="admin-panel")

# ============================================================
# 7. SUBSCRIBER INTROSPECTION
# ============================================================
print("\n--- Subscription Counts ---")
print(f"Subscriptions: {bus.get_subscribers()}\n")

# ============================================================
# 8. EVENT HISTORY
# ============================================================
print("--- Event History ---")
for event in bus.get_history(limit=5):
    print(f"  {event.name}: {event.data}")

print("\n--- User Events Only ---")
for event in bus.get_history("user.*", limit=3):
    print(f"  {event.name}: {event.data}")

# ============================================================
# 9. ERROR HANDLING
# ============================================================
print("\n--- Error Handling Test ---\n")

def buggy_handler(event: Event):
    raise ValueError("Intentional error in handler")

bus.subscribe("error.test", buggy_handler)
bus.publish("error.test", "This will trigger an error")

# ============================================================
# 10. CONVENIENT LAMBDA USAGE
# ============================================================
print("\n--- Lambda Subscribers ---\n")
bus.subscribe("payment.completed", lambda e: print(f"💰 Payment: ${e.data['amount']}"))
bus.publish("payment.completed", {"amount": 99.99, "currency": "USD"})

print("\n✨ All tests completed!")