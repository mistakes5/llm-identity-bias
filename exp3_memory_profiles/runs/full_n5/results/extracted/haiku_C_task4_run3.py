import re
import threading
from typing import Callable, Any, Dict, List, Optional
from functools import wraps
from dataclasses import dataclass
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class Event:
    """Represents an event with metadata."""
    name: str
    data: Any
    timestamp: datetime
    source: Optional[str] = None

    def __repr__(self) -> str:
        return f"Event(name={self.name!r}, data={self.data})"


class SubscriptionId:
    """Unique identifier for a subscription."""
    _counter = 0
    _lock = threading.Lock()

    def __init__(self):
        with SubscriptionId._lock:
            SubscriptionId._counter += 1
            self.id = SubscriptionId._counter

    def __repr__(self) -> str:
        return f"SubscriptionId({self.id})"

    def __eq__(self, other):
        return isinstance(other, SubscriptionId) and self.id == other.id

    def __hash__(self):
        return hash(self.id)


class EventBus:
    """
    Thread-safe publish-subscribe event bus with wildcard support.
    
    Supports exact event names and wildcard patterns using * and ? wildcards.
    """

    def __init__(self, strict_mode: bool = False):
        self._subscriptions: Dict[str, Dict[SubscriptionId, Callable]] = {}
        self._wildcard_subscriptions: Dict[str, Dict[SubscriptionId, Callable]] = {}
        self._lock = threading.RLock()
        self._event_history: List[Event] = []
        self._max_history = 1000
        self.strict_mode = strict_mode

    def subscribe(
        self,
        event_name: str,
        callback: Callable[[Event], None],
        use_wildcard: bool = False,
    ) -> SubscriptionId:
        """
        Subscribe to an event.
        
        Args:
            event_name: Event name or wildcard pattern (e.g., 'user.*')
            callback: Function that receives Event object
            use_wildcard: Force wildcard mode (auto-detected if event_name contains *)
            
        Returns:
            SubscriptionId for unsubscribe
        """
        sub_id = SubscriptionId()
        
        if '*' in event_name or '?' in event_name:
            use_wildcard = True

        with self._lock:
            if use_wildcard:
                if event_name not in self._wildcard_subscriptions:
                    self._wildcard_subscriptions[event_name] = {}
                self._wildcard_subscriptions[event_name][sub_id] = callback
                logger.info(f"Wildcard subscription: {event_name} -> {sub_id}")
            else:
                if event_name not in self._subscriptions:
                    self._subscriptions[event_name] = {}
                self._subscriptions[event_name][sub_id] = callback
                logger.info(f"Subscription: {event_name} -> {sub_id}")

        return sub_id

    def unsubscribe(self, event_name: str, sub_id: SubscriptionId) -> bool:
        """Unsubscribe from an event."""
        with self._lock:
            if event_name in self._subscriptions:
                if sub_id in self._subscriptions[event_name]:
                    del self._subscriptions[event_name][sub_id]
                    if not self._subscriptions[event_name]:
                        del self._subscriptions[event_name]
                    logger.info(f"Unsubscribed: {event_name} -> {sub_id}")
                    return True

            if event_name in self._wildcard_subscriptions:
                if sub_id in self._wildcard_subscriptions[event_name]:
                    del self._wildcard_subscriptions[event_name][sub_id]
                    if not self._wildcard_subscriptions[event_name]:
                        del self._wildcard_subscriptions[event_name]
                    return True

        return False

    def publish(self, event_name: str, data: Any = None, source: Optional[str] = None) -> Event:
        """Publish an event to all matching subscribers."""
        event = Event(name=event_name, data=data, timestamp=datetime.now(), source=source)

        with self._lock:
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history.pop(0)
            exact_subscribers = self._subscriptions.get(event_name, {}).copy()
            wildcard_patterns = self._wildcard_subscriptions.copy()

        executed_count = 0
        for callback in exact_subscribers.values():
            executed_count += self._call_callback(event_name, callback, event)

        for pattern, subscribers in wildcard_patterns.items():
            if self._matches_pattern(event_name, pattern):
                for callback in subscribers.values():
                    executed_count += self._call_callback(event_name, callback, event)

        logger.info(f"Published {event_name!r}: {executed_count} subscriber(s)")
        return event

    def _call_callback(self, event_name: str, callback: Callable, event: Event) -> int:
        """Execute callback safely. Returns 1 on success, 0 on failure."""
        try:
            callback(event)
            return 1
        except Exception as e:
            if self.strict_mode:
                logger.error(f"Callback error in {event_name}: {e}")
                raise
            else:
                logger.exception(f"Callback error in {event_name}")
                return 0

    @staticmethod
    def _matches_pattern(event_name: str, pattern: str) -> bool:
        """Check if event_name matches wildcard pattern using fnmatch rules."""
        regex_pattern = re.escape(pattern).replace(r'\*', '.*').replace(r'\?', '.')
        return re.fullmatch(regex_pattern, event_name) is not None

    def subscribe_once(
        self,
        event_name: str,
        callback: Callable[[Event], None],
        use_wildcard: bool = False,
    ) -> SubscriptionId:
        """Subscribe to event once, auto-unsubscribe after first call."""
        sub_id = SubscriptionId()

        @wraps(callback)
        def wrapper(event: Event):
            try:
                callback(event)
            finally:
                self.unsubscribe(event_name, sub_id)

        return self.subscribe(event_name, wrapper, use_wildcard=use_wildcard)

    def get_subscription_count(self, event_name: Optional[str] = None) -> int:
        """Get subscription count for specific event or all."""
        with self._lock:
            if event_name:
                exact = len(self._subscriptions.get(event_name, {}))
                wildcard = sum(
                    len(subs)
                    for pattern, subs in self._wildcard_subscriptions.items()
                    if self._matches_pattern(event_name, pattern)
                )
                return exact + wildcard
            else:
                total = sum(len(subs) for subs in self._subscriptions.values())
                total += sum(len(subs) for subs in self._wildcard_subscriptions.values())
                return total

    def get_event_history(self, event_name: Optional[str] = None) -> List[Event]:
        """Get event history, optionally filtered."""
        with self._lock:
            if event_name:
                return [e for e in self._event_history if e.name == event_name]
            return self._event_history.copy()

    def clear_subscriptions(self) -> None:
        """Remove all subscriptions."""
        with self._lock:
            self._subscriptions.clear()
            self._wildcard_subscriptions.clear()
        logger.info("All subscriptions cleared")

    def clear_history(self) -> None:
        """Clear event history."""
        with self._lock:
            self._event_history.clear()

    def __repr__(self) -> str:
        exact_count = sum(len(subs) for subs in self._subscriptions.values())
        wildcard_count = sum(len(subs) for subs in self._wildcard_subscriptions.values())
        return (
            f"EventBus(exact_subscriptions={exact_count}, "
            f"wildcard_subscriptions={wildcard_count}, "
            f"history_size={len(self._event_history)})"
        )

# Example 1: Basic subscription
bus = EventBus()

def on_user_created(event):
    print(f"User created: {event.data}")

sub_id = bus.subscribe('user.created', on_user_created)
bus.publish('user.created', {'id': 1, 'name': 'Alice'})

# Example 2: Wildcard subscriptions
def on_any_user_event(event):
    print(f"User event: {event.name} -> {event.data}")

bus.subscribe('user.*', on_any_user_event)
bus.publish('user.updated', {'id': 1})  # Matches user.*
bus.publish('user.deleted', {'id': 1})  # Matches user.*
bus.publish('order.created', {})        # Does NOT match user.*

# Example 3: Unsubscribe
bus.unsubscribe('user.created', sub_id)

# Example 4: Multiple subscribers per event
bus.subscribe('payment.completed', lambda e: print(f"[LOG] {e.name}"))
bus.subscribe('payment.completed', lambda e: print(f"[NOTIFY] {e.name}"))
bus.subscribe('payment.completed', lambda e: print(f"[SAVE] {e.name}"))
bus.publish('payment.completed', {'amount': 99.99})

# Example 5: Subscribe once
def startup_handler(event):
    print(f"App started: {event.data}")

bus.subscribe_once('app.startup', startup_handler)
bus.publish('app.startup', {'version': '1.0.0'})  # Handler called
bus.publish('app.startup', {'version': '1.0.1'})  # Handler NOT called

# Example 6: Event history
events = bus.get_event_history('user.created')
print(f"User created events: {events}")

# Example 7: Subscription count
print(f"Total subscribers: {bus.get_subscription_count()}")
print(f"Subscribers for 'user.created': {bus.get_subscription_count('user.created')}")

# Example 8: Complex wildcard patterns
bus.subscribe('*.created', lambda e: print(f"Entity created: {e.name}"))
bus.subscribe('user.account.*', lambda e: print(f"Account event: {e.name}"))