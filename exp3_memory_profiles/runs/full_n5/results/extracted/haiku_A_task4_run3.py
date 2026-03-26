"""
A flexible publish-subscribe event system with wildcard subscription support.

Features:
- Exact event matching and wildcard pattern matching
- Multiple subscribers per event
- Automatic unsubscribe with subscription IDs
- Thread-safe operations
- Exception isolation (one handler failure doesn't break others)
- Support for async handlers
"""

import asyncio
import threading
import uuid
from typing import Callable, Any, Dict, List, Optional, Pattern
from dataclasses import dataclass, field
from collections import defaultdict
import re
import traceback
from datetime import datetime


@dataclass
class Event:
    """Represents a published event."""
    name: str
    data: Any = None
    timestamp: datetime = field(default_factory=datetime.now)

    def __repr__(self) -> str:
        return f"Event(name={self.name!r}, data={self.data!r}, timestamp={self.timestamp})"


@dataclass
class Subscription:
    """Represents an active subscription."""
    id: str
    event_pattern: str
    handler: Callable
    is_wildcard: bool
    pattern_regex: Optional[Pattern] = None


class EventBus:
    """
    A publish-subscribe event system with wildcard support.
    Supports: exact ('user.created'), patterns ('user.*', '*.updated'), and catchall ('*')
    """

    def __init__(self, error_handler: Optional[Callable[[Exception, Event, Callable], None]] = None):
        self._subscriptions: Dict[str, List[Subscription]] = defaultdict(list)
        self._wildcard_subscriptions: List[Subscription] = []
        self._lock = threading.RLock()
        self._error_handler = error_handler or self._default_error_handler

    @staticmethod
    def _default_error_handler(exc: Exception, event: Event, handler: Callable) -> None:
        """Default error handler - prints traceback."""
        print(f"Error in subscriber for event {event.name}:")
        traceback.print_exc()

    @staticmethod
    def _pattern_to_regex(pattern: str) -> Pattern:
        """Convert wildcard pattern to compiled regex.
        
        Examples:
            'user.*' → matches 'user.created', 'user.deleted'
            'user.*.updated' → matches 'user.profile.updated'
            '*' → matches everything
        """
        escaped = re.escape(pattern).replace(r'\*', '.*')
        return re.compile(f"^{escaped}$")

    @staticmethod
    def _is_wildcard_pattern(pattern: str) -> bool:
        return '*' in pattern

    def subscribe(self, event_pattern: str, handler: Callable[[Event], Any], once: bool = False) -> str:
        """
        Subscribe to an event or event pattern.
        
        Returns: Subscription ID for later unsubscribe
        """
        subscription_id = str(uuid.uuid4())

        # Wrap handler if one-time subscription
        if once:
            original_handler = handler
            def wrapped_handler(event: Event) -> Any:
                result = original_handler(event)
                self.unsubscribe(subscription_id)
                return result
            handler = wrapped_handler

        is_wildcard = self._is_wildcard_pattern(event_pattern)
        pattern_regex = self._pattern_to_regex(event_pattern) if is_wildcard else None

        subscription = Subscription(
            id=subscription_id,
            event_pattern=event_pattern,
            handler=handler,
            is_wildcard=is_wildcard,
            pattern_regex=pattern_regex
        )

        with self._lock:
            if is_wildcard:
                self._wildcard_subscriptions.append(subscription)
            else:
                self._subscriptions[event_pattern].append(subscription)

        return subscription_id

    def subscribe_once(self, event_pattern: str, handler: Callable[[Event], Any]) -> str:
        """Subscribe for one-time use, auto-unsubscribe after match."""
        return self.subscribe(event_pattern, handler, once=True)

    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe using subscription ID. Returns True if found and removed."""
        with self._lock:
            for subscribers in self._subscriptions.values():
                for i, sub in enumerate(subscribers):
                    if sub.id == subscription_id:
                        subscribers.pop(i)
                        return True

            for i, sub in enumerate(self._wildcard_subscriptions):
                if sub.id == subscription_id:
                    self._wildcard_subscriptions.pop(i)
                    return True

        return False

    def unsubscribe_all(self, event_pattern: str) -> int:
        """Unsubscribe all handlers from an event pattern. Returns count removed."""
        count = 0
        with self._lock:
            if self._is_wildcard_pattern(event_pattern):
                self._wildcard_subscriptions = [
                    sub for sub in self._wildcard_subscriptions
                    if sub.event_pattern != event_pattern
                ]
                count = len([s for s in self._wildcard_subscriptions if s.event_pattern == event_pattern])
            else:
                if event_pattern in self._subscriptions:
                    count = len(self._subscriptions[event_pattern])
                    del self._subscriptions[event_pattern]

        return count

    def publish(self, event_name: str, data: Any = None) -> Event:
        """
        Publish an event to all matching subscribers.
        Returns: The published Event object
        """
        event = Event(name=event_name, data=data)

        with self._lock:
            exact_subs = self._subscriptions.get(event_name, [])[:]
            wildcard_subs = [sub for sub in self._wildcard_subscriptions 
                           if sub.pattern_regex.match(event_name)]
            all_subs = exact_subs + wildcard_subs

        # Execute handlers outside the lock
        for subscription in all_subs:
            try:
                subscription.handler(event)
            except Exception as exc:
                self._error_handler(exc, event, subscription.handler)

        return event

    async def publish_async(self, event_name: str, data: Any = None) -> Event:
        """Publish event and await all async subscribers."""
        event = Event(name=event_name, data=data)

        with self._lock:
            exact_subs = self._subscriptions.get(event_name, [])[:]
            wildcard_subs = [sub for sub in self._wildcard_subscriptions 
                           if sub.pattern_regex.match(event_name)]
            all_subs = exact_subs + wildcard_subs

        async def execute_handler(subscription: Subscription) -> None:
            try:
                result = subscription.handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:
                self._error_handler(exc, event, subscription.handler)

        await asyncio.gather(*[execute_handler(sub) for sub in all_subs])
        return event

    def get_subscribers(self, event_pattern: Optional[str] = None) -> Dict[str, List[str]]:
        """Get information about current subscriptions."""
        result = {}
        with self._lock:
            if event_pattern:
                if event_pattern in self._subscriptions:
                    result[event_pattern] = [
                        f"{sub.handler.__name__} ({sub.id[:8]}...)"
                        for sub in self._subscriptions[event_pattern]
                    ]
            else:
                for pattern, subs in self._subscriptions.items():
                    result[pattern] = [
                        f"{sub.handler.__name__} ({sub.id[:8]}...)"
                        for sub in subs
                    ]
                if self._wildcard_subscriptions:
                    result['[WILDCARDS]'] = [
                        f"{sub.event_pattern}: {sub.handler.__name__} ({sub.id[:8]}...)"
                        for sub in self._wildcard_subscriptions
                    ]
        return result

    def clear(self) -> None:
        """Clear all subscriptions."""
        with self._lock:
            self._subscriptions.clear()
            self._wildcard_subscriptions.clear()

# Basic usage
bus = EventBus()

def on_user_created(event):
    print(f"User created: {event.data}")

sub_id = bus.subscribe('user.created', on_user_created)
bus.publish('user.created', {'id': 1, 'name': 'Alice'})
bus.unsubscribe(sub_id)

# Wildcard subscriptions
bus.subscribe('user.*', lambda event: print(f"User event: {event.name}"))
bus.subscribe('*', lambda event: print(f"Global: {event.name}"))

bus.publish('user.created', {})      # Matches: user.*, *
bus.publish('user.deleted', {})      # Matches: user.*, *
bus.publish('order.placed', {})      # Matches: *

# One-time subscriptions
bus.subscribe_once('payment.processed', 
                  lambda event: print(f"Payment: {event.data}"))

# Error handling
def my_error_handler(exc, event, handler):
    print(f"Error in {handler.__name__}: {exc}")

bus = EventBus(error_handler=my_error_handler)

# Async support
async def async_handler(event):
    await some_async_operation(event.data)

bus.subscribe('order.*', async_handler)
await bus.publish_async('order.confirmed', {'id': 123})