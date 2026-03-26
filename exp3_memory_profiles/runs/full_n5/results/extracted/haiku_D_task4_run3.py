# pubsub.py
import threading
from typing import Callable, Any, Dict, List
from dataclasses import dataclass
from fnmatch import fnmatch
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)

@dataclass
class Event:
    """Represents a published event."""
    topic: str
    data: Any = None

class Subscription:
    """Represents a subscription with a unique ID."""
    def __init__(self, topic: str, handler: Callable, subscription_id: str = None):
        self.topic = topic
        self.handler = handler
        self.id = subscription_id or str(uuid4())

    def matches(self, event_topic: str) -> bool:
        """Check if this subscription matches an event topic (supports wildcards)."""
        return fnmatch(event_topic, self.topic)

    def __call__(self, event: Event) -> None:
        """Execute the handler for this subscription."""
        try:
            self.handler(event)
        except Exception as e:
            logger.error(f"Error in handler {self.id}: {e}", exc_info=True)

class EventSystem:
    """Thread-safe publish-subscribe event system."""
    
    def __init__(self):
        self._subscriptions: Dict[str, List[Subscription]] = {}
        self._wildcard_subscriptions: List[Subscription] = []
        self._lock = threading.RLock()
        self._publish_lock = threading.Lock()

    def subscribe(self, topic: str, handler: Callable[[Event], None], 
                  subscription_id: str = None) -> str:
        """Subscribe to a topic (supports wildcards: "user.*", "*.created")."""
        subscription = Subscription(topic, handler, subscription_id)
        
        with self._lock:
            if self._is_wildcard(topic):
                self._wildcard_subscriptions.append(subscription)
            else:
                if topic not in self._subscriptions:
                    self._subscriptions[topic] = []
                self._subscriptions[topic].append(subscription)
        
        return subscription.id

    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe by subscription ID."""
        with self._lock:
            # Check exact match subscriptions
            for topic, subscriptions in list(self._subscriptions.items()):
                for sub in subscriptions:
                    if sub.id == subscription_id:
                        subscriptions.remove(sub)
                        if not subscriptions:
                            del self._subscriptions[topic]
                        return True
            
            # Check wildcard subscriptions
            for sub in self._wildcard_subscriptions:
                if sub.id == subscription_id:
                    self._wildcard_subscriptions.remove(sub)
                    return True
        
        return False

    def publish(self, topic: str, data: Any = None) -> int:
        """Publish an event and return number of handlers invoked."""
        event = Event(topic=topic, data=data)
        handlers_invoked = 0
        
        with self._publish_lock:
            with self._lock:
                # Snapshot matching subscriptions (critical for thread safety)
                matching_subs = []
                if topic in self._subscriptions:
                    matching_subs.extend(self._subscriptions[topic])
                matching_subs.extend(
                    sub for sub in self._wildcard_subscriptions 
                    if sub.matches(topic)
                )
            
            # Invoke handlers OUTSIDE lock to prevent deadlocks
            for sub in matching_subs:
                sub(event)
                handlers_invoked += 1
        
        return handlers_invoked

    def clear(self) -> None:
        """Remove all subscriptions."""
        with self._lock:
            self._subscriptions.clear()
            self._wildcard_subscriptions.clear()

    def subscription_count(self, topic: str = None) -> int:
        """Count subscriptions (optionally for a specific topic)."""
        with self._lock:
            if topic is not None:
                exact = len(self._subscriptions.get(topic, []))
                wildcard = sum(1 for sub in self._wildcard_subscriptions 
                              if sub.matches(topic))
                return exact + wildcard
            else:
                exact = sum(len(subs) for subs in self._subscriptions.values())
                return exact + len(self._wildcard_subscriptions)

    def get_subscriptions(self, topic: str = None) -> List[Subscription]:
        """Get subscriptions (optionally filtered by topic)."""
        with self._lock:
            if topic is None:
                all_subs = []
                for subs in self._subscriptions.values():
                    all_subs.extend(subs)
                all_subs.extend(self._wildcard_subscriptions)
                return all_subs
            else:
                matching = []
                if topic in self._subscriptions:
                    matching.extend(self._subscriptions[topic])
                matching.extend(sub for sub in self._wildcard_subscriptions 
                               if sub.matches(topic))
                return matching

    @staticmethod
    def _is_wildcard(topic: str) -> bool:
        """Check if a topic contains wildcard patterns."""
        return "*" in topic or "?" in topic

# Convenience singleton
_default_system = EventSystem()

def subscribe(topic: str, handler: Callable[[Event], None]) -> str:
    return _default_system.subscribe(topic, handler)

def unsubscribe(subscription_id: str) -> bool:
    return _default_system.unsubscribe(subscription_id)

def publish(topic: str, data: Any = None) -> int:
    return _default_system.publish(topic, data)

from pubsub import subscribe, publish, Event

def on_user_created(event: Event):
    print(f"User created: {event.data}")

# Subscribe
sub_id = subscribe("user.created", on_user_created)

# Publish
publish("user.created", {"user_id": 123, "name": "Alice"})

# Unsubscribe
unsubscribe(sub_id)

def on_user_event(event: Event):
    print(f"User event: {event.topic}")

subscribe("user.*", on_user_event)

publish("user.created", {...})    # Matches
publish("user.deleted", {...})    # Matches
publish("order.created", {...})   # Does NOT match

def logger(event: Event):
    print(f"[LOG] {event.topic}: {event.data}")

def analytics(event: Event):
    print(f"[ANALYTICS] Event tracked: {event.topic}")

def database(event: Event):
    print(f"[DB] Persisting: {event.topic}")

subscribe("order.completed", logger)
subscribe("order.completed", analytics)
subscribe("order.completed", database)

# All three handlers invoked
publish("order.completed", {"order_id": 456})

from pubsub import EventSystem

# Separate systems for different domains
user_events = EventSystem()
order_events = EventSystem()

user_events.subscribe("auth.login", on_login)
order_events.subscribe("*.created", on_order_created)

user_events.publish("auth.login", {"user": "bob"})
order_events.publish("order.created", {"id": 789})

def bad_handler(event: Event):
    raise ValueError("Intentional error")

def good_handler(event: Event):
    print("Still executes even if another handler fails")

subscribe("event", bad_handler)
subscribe("event", good_handler)

# Both handlers run; error in bad_handler doesn't affect good_handler
publish("event", {})