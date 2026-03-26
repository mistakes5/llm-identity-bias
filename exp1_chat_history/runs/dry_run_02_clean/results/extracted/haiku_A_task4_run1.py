import threading
from typing import Callable, Any, Dict, List, Set
from fnmatch import fnmatch


class EventBus:
    """
    A publish-subscribe event system with support for wildcard subscriptions.
    
    Thread-safe implementation for subscribing to events, publishing events with data,
    and unsubscribing. Supports wildcard patterns like "user.*" or "*.created".
    """
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._lock = threading.RLock()
    
    def subscribe(self, event_pattern: str, callback: Callable[[str, Any], None]) -> str:
        """
        Subscribe to an event pattern.
        
        Args:
            event_pattern: Event name or wildcard pattern (e.g., "user.created", "user.*", "*.error")
            callback: Function to call when event matches. Receives (event_name, data)
        
        Returns:
            subscription_id: Unique ID for unsubscribing
        """
        with self._lock:
            if event_pattern not in self._subscribers:
                self._subscribers[event_pattern] = []
            
            self._subscribers[event_pattern].append(callback)
            # Return a subscription ID combining pattern and callback
            subscription_id = f"{event_pattern}:{id(callback)}"
            return subscription_id
    
    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from an event.
        
        Args:
            subscription_id: The ID returned from subscribe()
        
        Returns:
            True if unsubscribed, False if subscription not found
        """
        with self._lock:
            pattern, callback_id = subscription_id.rsplit(':', 1)
            
            if pattern not in self._subscribers:
                return False
            
            callbacks = self._subscribers[pattern]
            # Find and remove the callback with matching ID
            for i, cb in enumerate(callbacks):
                if str(id(cb)) == callback_id:
                    callbacks.pop(i)
                    # Clean up empty patterns
                    if not callbacks:
                        del self._subscribers[pattern]
                    return True
            
            return False
    
    def publish(self, event_name: str, data: Any = None) -> int:
        """
        Publish an event to all matching subscribers.
        
        Args:
            event_name: Event name (e.g., "user.created")
            data: Optional data to pass to subscribers
        
        Returns:
            Number of subscribers that were called
        """
        with self._lock:
            # Create a copy to avoid issues if callbacks modify subscribers
            patterns = list(self._subscribers.keys())
        
        callback_count = 0
        for pattern in patterns:
            # Check if event name matches the pattern (including exact matches)
            if fnmatch(event_name, pattern):
                with self._lock:
                    # Get fresh list in case it changed
                    callbacks = self._subscribers.get(pattern, [])[:]
                
                for callback in callbacks:
                    try:
                        callback(event_name, data)
                        callback_count += 1
                    except Exception as e:
                        # Log but don't crash on callback errors
                        print(f"Error in callback for {pattern}: {e}")
        
        return callback_count
    
    def clear(self):
        """Remove all subscribers."""
        with self._lock:
            self._subscribers.clear()


# Example usage and testing
if __name__ == "__main__":
    bus = EventBus()
    
    # Define some callbacks
    def on_user_created(event_name, data):
        print(f"✓ {event_name}: User {data['username']} created")
    
    def on_user_event(event_name, data):
        print(f"  └─ Generic user handler: {event_name}")
    
    def on_any_error(event_name, data):
        print(f"⚠ ALERT {event_name}: {data['message']}")
    
    # Subscribe to specific events and patterns
    sub1 = bus.subscribe("user.created", on_user_created)
    sub2 = bus.subscribe("user.*", on_user_event)
    sub3 = bus.subscribe("*.error", on_any_error)
    
    print("--- Publishing Events ---\n")
    
    # Publish exact match
    bus.publish("user.created", {"username": "alice", "email": "alice@example.com"})
    print()
    
    # Publish wildcard match
    bus.publish("user.updated", {"username": "bob", "changes": ["email"]})
    print()
    
    # Publish error event
    bus.publish("db.error", {"message": "Connection timeout", "code": 500})
    print()
    
    # Publish event with no subscribers
    count = bus.publish("payment.processed", {"amount": 99.99})
    print(f"payment.processed matched {count} subscribers\n")
    
    # Unsubscribe and verify
    print("--- After Unsubscribing from user.* ---\n")
    bus.unsubscribe(sub2)
    bus.publish("user.deleted", {"username": "charlie"})