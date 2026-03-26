from typing import Callable, Any, Dict, List, Set
from dataclasses import dataclass
import fnmatch
from threading import Lock


@dataclass
class Event:
    """Represents an event with a name and associated data."""
    name: str
    data: Any = None


class EventBus:
    """
    A publish-subscribe event system supporting pattern-based subscriptions.
    
    Features:
    - Subscribe to specific events or event patterns (with wildcards)
    - Publish events with arbitrary data
    - Unsubscribe from events
    - Thread-safe operations
    """
    
    def __init__(self):
        self._subscribers: Dict[str, Set[Callable]] = {}
        self._pattern_subscribers: Dict[str, Set[Callable]] = {}
        self._lock = Lock()
    
    def subscribe(self, event_name: str, handler: Callable[[Event], None]) -> Callable:
        """
        Subscribe to an event or event pattern.
        
        Supports wildcards:
        - "user.created" - exact match
        - "user.*" - matches "user.created", "user.updated", etc.
        - "*" - matches all events
        
        Returns an unsubscribe function for convenience.
        """
        with self._lock:
            if self._is_pattern(event_name):
                if event_name not in self._pattern_subscribers:
                    self._pattern_subscribers[event_name] = set()
                self._pattern_subscribers[event_name].add(handler)
            else:
                if event_name not in self._subscribers:
                    self._subscribers[event_name] = set()
                self._subscribers[event_name].add(handler)
        
        # Return an unsubscribe function
        return lambda: self.unsubscribe(event_name, handler)
    
    def unsubscribe(self, event_name: str, handler: Callable[[Event], None]) -> bool:
        """
        Unsubscribe a handler from an event.
        Returns True if the handler was found and removed, False otherwise.
        """
        with self._lock:
            if self._is_pattern(event_name):
                if event_name in self._pattern_subscribers:
                    if handler in self._pattern_subscribers[event_name]:
                        self._pattern_subscribers[event_name].remove(handler)
                        if not self._pattern_subscribers[event_name]:
                            del self._pattern_subscribers[event_name]
                        return True
            else:
                if event_name in self._subscribers:
                    if handler in self._subscribers[event_name]:
                        self._subscribers[event_name].remove(handler)
                        if not self._subscribers[event_name]:
                            del self._subscribers[event_name]
                        return True
        return False
    
    def publish(self, event_name: str, data: Any = None) -> None:
        """
        Publish an event to all matching subscribers.
        """
        event = Event(name=event_name, data=data)
        
        with self._lock:
            # Get a snapshot of handlers to avoid issues if unsubscribe happens during iteration
            handlers: List[Callable] = []
            
            # Add exact match subscribers
            if event_name in self._subscribers:
                handlers.extend(self._subscribers[event_name])
            
            # Add pattern match subscribers
            for pattern, pattern_handlers in self._pattern_subscribers.items():
                if fnmatch.fnmatch(event_name, pattern):
                    handlers.extend(pattern_handlers)
        
        # Call handlers outside the lock
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                print(f"Error calling handler for event '{event_name}': {e}")
    
    def _is_pattern(self, event_name: str) -> bool:
        """Check if an event name contains wildcard characters."""
        return "*" in event_name or "?" in event_name
    
    def get_subscriber_count(self, event_name: str = None) -> int:
        """
        Get the number of subscribers for a specific event or all events.
        """
        with self._lock:
            if event_name is None:
                exact = sum(len(handlers) for handlers in self._subscribers.values())
                pattern = sum(len(handlers) for handlers in self._pattern_subscribers.values())
                return exact + pattern
            else:
                count = len(self._subscribers.get(event_name, set()))
                # Count pattern matches
                for pattern in self._pattern_subscribers:
                    if fnmatch.fnmatch(event_name, pattern):
                        count += len(self._pattern_subscribers[pattern])
                return count


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    bus = EventBus()
    
    # Define handlers
    def on_user_created(event: Event):
        print(f"✓ User created: {event.data}")
    
    def on_user_deleted(event: Event):
        print(f"✓ User deleted: {event.data}")
    
    def on_any_user_event(event: Event):
        print(f"  [Pattern handler] Event '{event.name}' with data: {event.data}")
    
    def on_any_event(event: Event):
        print(f"  [Wildcard] Any event: {event.name}")
    
    # Subscribe to specific events
    bus.subscribe("user.created", on_user_created)
    bus.subscribe("user.deleted", on_user_deleted)
    
    # Subscribe to event patterns
    bus.subscribe("user.*", on_any_user_event)
    bus.subscribe("*", on_any_event)
    
    print("=== Publishing Events ===")
    bus.publish("user.created", {"id": 1, "name": "Alice"})
    bus.publish("user.deleted", {"id": 2, "name": "Bob"})
    bus.publish("user.updated", {"id": 1, "name": "Alice Updated"})
    bus.publish("system.startup", {})
    
    print(f"\n=== Subscriber Counts ===")
    print(f"Total subscribers: {bus.get_subscriber_count()}")
    print(f"Subscribers for 'user.created': {bus.get_subscriber_count('user.created')}")
    print(f"Subscribers for 'user.*': {bus.get_subscriber_count('user.updated')}")
    
    print("\n=== Unsubscribing ===")
    bus.unsubscribe("user.created", on_user_created)
    bus.publish("user.created", {"id": 3, "name": "Charlie"})
    
    print("\n=== Using Unsubscribe Function ===")
    unsub = bus.subscribe("test.event", lambda e: print(f"Test: {e.data}"))
    bus.publish("test.event", "Before unsubscribe")
    unsub()  # Call the returned unsubscribe function
    bus.publish("test.event", "After unsubscribe (won't print)")

bus.subscribe("user.created", handler)      # Exact event
bus.subscribe("user.*", handler)             # All user events
bus.subscribe("*.created", handler)          # All "created" events
bus.subscribe("*", handler)                  # All events