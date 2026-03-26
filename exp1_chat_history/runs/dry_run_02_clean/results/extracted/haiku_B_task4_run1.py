import threading
from typing import Callable, Any, Dict, List, Set
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Event:
    """Event object containing metadata."""
    name: str
    data: Any
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class EventBus:
    """Thread-safe publish-subscribe event system with wildcard support."""
    
    def __init__(self):
        self._subscriptions: Dict[str, List[Callable]] = {}  # Exact matches
        self._wildcard_subscriptions: Dict[str, List[Callable]] = {}  # Pattern matches
        self._lock = threading.RLock()
    
    def subscribe(self, event_name: str, callback: Callable) -> None:
        """
        Subscribe to an event.
        
        Args:
            event_name: Event name to subscribe to. Use wildcards like "user.*" 
                       to match all events starting with "user."
            callback: Function to call when event is published. 
                     Receives (event_name: str, data: Any)
        
        Raises:
            ValueError: If callback is not callable.
        """
        if not callable(callback):
            raise ValueError(f"Callback must be callable, got {type(callback)}")
        
        with self._lock:
            if self._is_wildcard(event_name):
                if event_name not in self._wildcard_subscriptions:
                    self._wildcard_subscriptions[event_name] = []
                self._wildcard_subscriptions[event_name].append(callback)
            else:
                if event_name not in self._subscriptions:
                    self._subscriptions[event_name] = []
                self._subscriptions[event_name].append(callback)
    
    def unsubscribe(self, event_name: str, callback: Callable) -> bool:
        """
        Unsubscribe a callback from an event.
        
        Args:
            event_name: Event name to unsubscribe from.
            callback: The callback function to remove.
        
        Returns:
            True if callback was found and removed, False otherwise.
        """
        with self._lock:
            if self._is_wildcard(event_name):
                subscriptions = self._wildcard_subscriptions.get(event_name, [])
            else:
                subscriptions = self._subscriptions.get(event_name, [])
            
            try:
                subscriptions.remove(callback)
                return True
            except ValueError:
                return False
    
    def publish(self, event_name: str, data: Any = None) -> None:
        """
        Publish an event to all subscribers.
        
        Args:
            event_name: Name of the event.
            data: Optional data to pass to subscribers.
        """
        event = Event(name=event_name, data=data)
        
        with self._lock:
            # Get exact match subscribers
            exact_callbacks = self._subscriptions.get(event_name, [])[:]
            
            # Get wildcard subscribers that match this event
            wildcard_callbacks = []
            for pattern, callbacks in self._wildcard_subscriptions.items():
                if self._matches_pattern(event_name, pattern):
                    wildcard_callbacks.extend(callbacks)
        
        # Execute callbacks outside the lock to prevent deadlocks
        for callback in exact_callbacks:
            try:
                callback(event_name, data)
            except Exception as e:
                # Log but don't raise — keep publishing to other subscribers
                print(f"Error in callback for '{event_name}': {e}")
        
        for callback in wildcard_callbacks:
            try:
                callback(event_name, data)
            except Exception as e:
                print(f"Error in wildcard callback for '{event_name}': {e}")
    
    def unsubscribe_all(self, event_name: str) -> int:
        """
        Remove all subscribers from an event.
        
        Args:
            event_name: Event name to clear.
        
        Returns:
            Number of subscribers removed.
        """
        with self._lock:
            if self._is_wildcard(event_name):
                count = len(self._wildcard_subscriptions.pop(event_name, []))
            else:
                count = len(self._subscriptions.pop(event_name, []))
        return count
    
    def subscriber_count(self, event_name: str) -> int:
        """Get the number of subscribers for an event (exact matches only)."""
        with self._lock:
            if self._is_wildcard(event_name):
                return len(self._wildcard_subscriptions.get(event_name, []))
            else:
                return len(self._subscriptions.get(event_name, []))
    
    @staticmethod
    def _is_wildcard(event_name: str) -> bool:
        """Check if event name contains wildcard pattern."""
        return "*" in event_name
    
    @staticmethod
    def _matches_pattern(event_name: str, pattern: str) -> bool:
        """
        Check if an event name matches a wildcard pattern.
        
        Examples:
            "user.login" matches "user.*"
            "user.account.created" matches "user.*" (prefix match)
            "admin.login" does NOT match "user.*"
        """
        if not pattern.endswith("*"):
            return False
        
        prefix = pattern[:-1]  # Remove the "*"
        return event_name.startswith(prefix)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    bus = EventBus()
    
    # Exact subscription
    def log_login(event_name, data):
        print(f"[LOGIN] User: {data.get('username')} at {data.get('timestamp')}")
    
    # Wildcard subscription
    def log_all_user_events(event_name, data):
        print(f"[USER EVENT] {event_name}: {data}")
    
    # Another wildcard for all events
    def audit_log(event_name, data):
        print(f"[AUDIT] {event_name}")
    
    # Subscribe
    bus.subscribe("user.login", log_login)
    bus.subscribe("user.*", log_all_user_events)
    bus.subscribe("*", audit_log)
    
    print("=== Publishing user.login ===")
    bus.publish("user.login", {"username": "alice", "timestamp": "14:32:00"})
    
    print("\n=== Publishing user.logout ===")
    bus.publish("user.logout", {"username": "alice", "timestamp": "14:45:00"})
    
    print("\n=== Publishing admin.settings_changed ===")
    bus.publish("admin.settings_changed", {"setting": "max_users", "value": 1000})
    
    print("\n=== Unsubscribing from user.login ===")
    bus.unsubscribe("user.login", log_login)
    
    print("\n=== Publishing user.login again ===")
    bus.publish("user.login", {"username": "bob", "timestamp": "15:00:00"})
    
    print(f"\n=== Subscriber counts ===")
    print(f"user.login: {bus.subscriber_count('user.login')}")
    print(f"user.*: {bus.subscriber_count('user.*')}")