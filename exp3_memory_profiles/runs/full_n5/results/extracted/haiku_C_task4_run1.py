# pubsub.py
from typing import Callable, Any, Dict
from dataclasses import dataclass
from fnmatch import fnmatch
from threading import RLock
from functools import wraps


@dataclass
class Event:
    """Represents a published event with metadata."""
    name: str
    data: Any = None

    def __repr__(self) -> str:
        return f"Event(name={self.name!r}, data={self.data!r})"


class EventBus:
    """
    A thread-safe publish-subscribe event bus with wildcard pattern support.

    Features:
    - Subscribe to specific events or wildcard patterns
    - Publish events with arbitrary data
    - Unsubscribe individual listeners or all listeners for an event
    - Exception handling with optional error callbacks
    """

    def __init__(self):
        """Initialize the event bus."""
        self._subscribers: Dict[str, list] = {}
        self._lock = RLock()
        self._error_handler = None

    def on(self, event_pattern: str, callback: Callable) -> Callable:
        """
        Subscribe to an event or wildcard pattern.

        Args:
            event_pattern: Event name or wildcard pattern (e.g., "user.*", "user.created")
            callback: Function to call when event is published. Receives Event object.

        Returns:
            Unsubscribe function that removes this specific listener.
        """
        with self._lock:
            if event_pattern not in self._subscribers:
                self._subscribers[event_pattern] = []
            self._subscribers[event_pattern].append(callback)

        return lambda: self.off(event_pattern, callback)

    def once(self, event_pattern: str, callback: Callable) -> Callable:
        """Subscribe to an event once, then auto-unsubscribe."""
        @wraps(callback)
        def one_time_wrapper(event: Event):
            try:
                callback(event)
            finally:
                self.off(event_pattern, one_time_wrapper)

        return self.on(event_pattern, one_time_wrapper)

    def off(self, event_pattern: str, callback: Callable | None = None) -> None:
        """
        Unsubscribe from an event pattern.

        Args:
            event_pattern: Event name or pattern to unsubscribe from
            callback: Specific callback to remove. If None, removes all listeners.
        """
        with self._lock:
            if event_pattern not in self._subscribers:
                return

            if callback is None:
                self._subscribers[event_pattern].clear()
            else:
                try:
                    self._subscribers[event_pattern].remove(callback)
                except ValueError:
                    pass

    def emit(self, event_name: str, data: Any = None) -> None:
        """
        Publish an event to all matching subscribers.

        Args:
            event_name: Name of the event to publish
            data: Data to pass to subscribers
        """
        event = Event(name=event_name, data=data)

        with self._lock:
            patterns = list(self._subscribers.keys())

        for pattern in patterns:
            # fnmatch does Unix shell-style wildcard matching
            if fnmatch(event_name, pattern):
                with self._lock:
                    callbacks = list(self._subscribers.get(pattern, []))

                for callback in callbacks:
                    try:
                        callback(event)
                    except Exception as e:
                        self._handle_error(pattern, e)

    def publish(self, event_name: str, data: Any = None) -> None:
        """Alias for emit()."""
        self.emit(event_name, data)

    def set_error_handler(self, handler: Callable) -> None:
        """Set a global error handler for callback exceptions."""
        self._error_handler = handler

    def _handle_error(self, event_pattern: str, exception: Exception) -> None:
        """Internal error handling."""
        if self._error_handler:
            try:
                self._error_handler(event_pattern, exception)
            except Exception:
                print(f"Error handler failed: {exception}")
        else:
            print(f"Error in {event_pattern}: {exception}")

    def listeners(self, event_pattern: str | None = None) -> Dict[str, int]:
        """Get listener count for patterns."""
        with self._lock:
            if event_pattern:
                count = len(self._subscribers.get(event_pattern, []))
                return {event_pattern: count}

            return {
                pattern: len(callbacks)
                for pattern, callbacks in self._subscribers.items()
                if callbacks
            }

    def clear(self) -> None:
        """Remove all subscribers."""
        with self._lock:
            self._subscribers.clear()

from pubsub import EventBus, Event

# Create event bus
bus = EventBus()

# 1. Basic subscription
bus.on("user.created", lambda event: print(f"New user: {event.data}"))
bus.emit("user.created", {"id": 1, "name": "Alice"})

# 2. Wildcard patterns
bus.on("user.*", lambda event: print(f"User event: {event.name}"))
bus.emit("user.updated", {"id": 1})     # Matches
bus.emit("user.deleted", {"id": 1})     # Matches
bus.emit("admin.created", {})            # Doesn't match

# 3. One-time subscription
bus.once("app.startup", lambda event: print("Starting app"))
bus.emit("app.startup", {})              # Prints
bus.emit("app.startup", {})              # No output

# 4. Unsubscribe
unsub = bus.on("order.placed", lambda event: print("Order placed"))
bus.emit("order.placed", {})             # Prints
unsub()                                   # Unsubscribe
bus.emit("order.placed", {})             # No output

# 5. Error handling
def handle_error(pattern, exc):
    print(f"Error in {pattern}: {exc}")

bus.set_error_handler(handle_error)
bus.on("risky", lambda e: 1/0)           # Will call error handler
bus.emit("risky", {})

# 6. Complex patterns
bus.on("api.*.users.get", lambda e: print(f"GET {e.name}"))
bus.emit("api.v1.users.get", {})         # Matches

# 7. Inspect listeners
print(bus.listeners())  # {'user.*': 1, 'order.placed': 0}