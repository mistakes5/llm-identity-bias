"""
Publish-Subscribe Event System

A flexible event bus supporting direct subscriptions, wildcard patterns,
and multiple callback execution strategies.
"""

from typing import Any, Callable, Dict, List, Optional
from collections import defaultdict
from fnmatch import fnmatch
import threading
from dataclasses import dataclass
from enum import Enum


class ErrorStrategy(Enum):
    """How to handle exceptions raised by callbacks."""
    ISOLATE = "isolate"      # Catch exceptions, log, continue with other callbacks
    FAIL_FAST = "fail_fast"  # Stop on first exception, re-raise it
    SILENT = "silent"        # Silently ignore all exceptions


@dataclass
class Subscription:
    """Represents a single subscription."""
    callback: Callable
    pattern: str
    is_wildcard: bool


class EventBus:
    """
    A thread-safe publish-subscribe event bus with wildcard support.

    Features:
    - Direct event subscriptions: bus.subscribe('user.login', callback)
    - Wildcard subscriptions: bus.subscribe('user.*', callback)
    - Pattern matching: Supports fnmatch shell-style patterns
    - Thread-safe by default
    - Configurable error handling strategy
    """

    def __init__(self, error_strategy: ErrorStrategy = ErrorStrategy.ISOLATE):
        """
        Initialize the event bus.

        Args:
            error_strategy: How to handle exceptions in callbacks
                - ISOLATE: Catch exceptions, log them, continue with other callbacks (default)
                - FAIL_FAST: Stop on first exception and re-raise it
                - SILENT: Ignore all exceptions silently
        """
        self._subscriptions: Dict[str, List[Subscription]] = defaultdict(list)
        self._wildcard_subscriptions: List[Subscription] = []
        self._lock = threading.RLock()
        self.error_strategy = error_strategy
        self._exception_handlers: List[Callable[[str, Exception], None]] = []

    def subscribe(self, event: str, callback: Callable) -> Callable:
        """
        Subscribe to an event or wildcard pattern.

        Args:
            event: Event name or pattern (e.g., 'user.login' or 'user.*')
            callback: Function to call when event is published

        Returns:
            The callback (for convenient use as decorator)
        """
        with self._lock:
            is_wildcard = '*' in event or '?' in event
            subscription = Subscription(callback, event, is_wildcard)

            if is_wildcard:
                self._wildcard_subscriptions.append(subscription)
            else:
                self._subscriptions[event].append(subscription)

        return callback

    def unsubscribe(self, event: str, callback: Callable) -> bool:
        """
        Unsubscribe a callback from an event.

        Args:
            event: Event name or pattern that was used in subscribe()
            callback: The callback function to remove

        Returns:
            True if callback was found and removed, False otherwise
        """
        with self._lock:
            is_wildcard = '*' in event or '?' in event

            if is_wildcard:
                for i, sub in enumerate(self._wildcard_subscriptions):
                    if sub.callback == callback and sub.pattern == event:
                        self._wildcard_subscriptions.pop(i)
                        return True
                return False
            else:
                subs = self._subscriptions[event]
                for i, sub in enumerate(subs):
                    if sub.callback == callback:
                        subs.pop(i)
                        if not subs:
                            del self._subscriptions[event]
                        return True
                return False

    def unsubscribe_all(self, event: str) -> int:
        """
        Unsubscribe all callbacks from an event.

        Args:
            event: Event name or pattern

        Returns:
            Number of callbacks removed
        """
        with self._lock:
            is_wildcard = '*' in event or '?' in event
            removed = 0

            if is_wildcard:
                removed = len([s for s in self._wildcard_subscriptions if s.pattern == event])
                self._wildcard_subscriptions = [
                    s for s in self._wildcard_subscriptions if s.pattern != event
                ]
            else:
                removed = len(self._subscriptions.get(event, []))
                if event in self._subscriptions:
                    del self._subscriptions[event]

            return removed

    def publish(self, event: str, data: Any = None) -> int:
        """
        Publish an event to all subscribed callbacks.

        Args:
            event: Event name to publish
            data: Optional data to pass to callbacks

        Returns:
            Number of callbacks executed

        Raises:
            Exception: If error_strategy is FAIL_FAST and a callback raises
        """
        with self._lock:
            subscriptions_to_call = list(self._subscriptions.get(event, []))
            for sub in self._wildcard_subscriptions:
                if fnmatch(event, sub.pattern):
                    subscriptions_to_call.append(sub)

        executed = 0
        for sub in subscriptions_to_call:
            try:
                sub.callback(data)
                executed += 1
            except Exception as e:
                self._handle_callback_exception(event, e)
                if self.error_strategy == ErrorStrategy.FAIL_FAST:
                    raise

        return executed

    def has_subscribers(self, event: str) -> bool:
        """Check if an event has any subscribers (direct or wildcard)."""
        with self._lock:
            if event in self._subscriptions and self._subscriptions[event]:
                return True
            for sub in self._wildcard_subscriptions:
                if fnmatch(event, sub.pattern):
                    return True
        return False

    def subscriber_count(self, event: Optional[str] = None) -> int:
        """Count subscribers for an event or total across all events."""
        with self._lock:
            if event is None:
                total = sum(len(subs) for subs in self._subscriptions.values())
                total += len(self._wildcard_subscriptions)
                return total
            else:
                count = len(self._subscriptions.get(event, []))
                count += sum(1 for sub in self._wildcard_subscriptions if fnmatch(event, sub.pattern))
                return count

    def on_exception(self, handler: Callable[[str, Exception], None]) -> Callable:
        """Register a handler for exceptions raised by callbacks."""
        self._exception_handlers.append(handler)
        return handler

    def clear(self) -> None:
        """Remove all subscriptions from the event bus."""
        with self._lock:
            self._subscriptions.clear()
            self._wildcard_subscriptions.clear()

    def _handle_callback_exception(self, event: str, exc: Exception) -> None:
        """Handle exceptions raised during callback execution."""
        if self.error_strategy == ErrorStrategy.ISOLATE:
            for handler in self._exception_handlers:
                try:
                    handler(event, exc)
                except Exception:
                    pass

# Basic usage
bus = EventBus()

# Subscribe with decorator
@bus.subscribe('user.login')
def handle_login(data):
    print(f"User logged in: {data}")

# Or subscribe with function call
def handle_logout(data):
    print(f"User logged out: {data}")
bus.subscribe('user.logout', handle_logout)

# Publish events
bus.publish('user.login', {'user_id': 123, 'email': 'alice@example.com'})

# Wildcard subscriptions
@bus.subscribe('user.*')
def handle_any_user_event(data):
    print(f"User event: {data}")

# Unsubscribe
bus.unsubscribe('user.logout', handle_logout)

# Check subscribers
if bus.has_subscribers('user.login'):
    count = bus.subscriber_count('user.login')
    print(f"{count} handlers listening to user.login")

# Exception handling
@bus.on_exception
def log_error(event, exc):
    print(f"Error in {event}: {exc}")

# Different error strategies
bus_fail_fast = EventBus(error_strategy=ErrorStrategy.FAIL_FAST)
bus_silent = EventBus(error_strategy=ErrorStrategy.SILENT)