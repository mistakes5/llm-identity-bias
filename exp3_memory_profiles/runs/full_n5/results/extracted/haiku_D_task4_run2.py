"""
Thread-safe publish-subscribe event system with wildcard support.

Supports:
- Exact event subscriptions: bus.subscribe("user.created", handler)
- Wildcard subscriptions: bus.subscribe("user.*", handler)
- Glob patterns: bus.subscribe("*.updated", handler)
"""

import re
import threading
from typing import Callable, Any, Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class Event:
    """Immutable event object."""
    name: str
    data: Dict[str, Any] = field(default_factory=dict)


class PatternMatcher:
    """Converts wildcard patterns to regex for efficient matching."""

    _cache: Dict[str, re.Pattern] = {}
    _cache_lock = threading.Lock()

    @classmethod
    def matches(cls, pattern: str, event_name: str) -> bool:
        """Check if event_name matches wildcard pattern."""
        if pattern == event_name:
            return True
        if '*' not in pattern:
            return False

        regex = cls._get_regex(pattern)
        return bool(regex.match(event_name))

    @classmethod
    def _get_regex(cls, pattern: str) -> re.Pattern:
        """Get or create cached regex for pattern."""
        if pattern in cls._cache:
            return cls._cache[pattern]

        # Convert glob to regex: * → [^.]* (match anything except dots)
        escaped = re.escape(pattern)
        regex_str = escaped.replace(r'\*', '[^.]*')
        regex = re.compile(f'^{regex_str}$')

        with cls._cache_lock:
            cls._cache[pattern] = regex

        return regex


class EventBus:
    """
    Thread-safe pub-sub event bus with wildcard pattern support.

    Example:
        bus = EventBus()
        bus.subscribe("user.created", lambda e: print(f"User: {e.data}"))
        bus.subscribe("user.*", lambda e: print(f"Event: {e.name}"))
        bus.publish("user.created", {"id": 123})
    """

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._pattern_subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._lock = threading.RLock()
        self._published_count = 0

    def subscribe(self, event_pattern: str, handler: Callable[..., Any],
                  once: bool = False) -> 'Subscription':
        """
        Subscribe to events matching a pattern.

        Args:
            event_pattern: Event name or wildcard (e.g., "user.*")
            handler: Callable receiving Event object
            once: Unsubscribe after first match

        Returns:
            Subscription for easy unsubscription
        """
        if not callable(handler):
            raise TypeError(f"Handler must be callable, got {type(handler).__name__}")

        with self._lock:
            # Wrap for once=True behavior
            if once:
                original = handler
                def once_wrapper(event):
                    result = original(event)
                    self.unsubscribe(event_pattern, once_wrapper)
                    return result
                handler = once_wrapper

            # Store in appropriate bucket
            subscribers = (self._pattern_subscribers[event_pattern]
                          if '*' in event_pattern else self._subscribers[event_pattern])
            subscribers.append(handler)

            return Subscription(self, event_pattern, handler)

    def unsubscribe(self, event_pattern: str, handler: Callable) -> bool:
        """Unsubscribe handler from pattern. Returns True if found."""
        with self._lock:
            is_pattern = '*' in event_pattern
            subscribers = (self._pattern_subscribers[event_pattern]
                          if is_pattern else self._subscribers[event_pattern])
            try:
                subscribers.remove(handler)
                if not subscribers:
                    if is_pattern:
                        del self._pattern_subscribers[event_pattern]
                    else:
                        del self._subscribers[event_pattern]
                return True
            except ValueError:
                return False

    def publish(self, event_name: str, data: Optional[Dict[str, Any]] = None,
                error_handler: Optional[Callable[[str, Exception], None]] = None) -> int:
        """
        Publish event to all matching subscribers.

        Args:
            event_name: Event name to publish
            data: Event payload
            error_handler: Optional callable(event_name, exception) for errors

        Returns:
            Number of handlers executed successfully
        """
        if not event_name or not isinstance(event_name, str):
            raise ValueError(f"event_name must be non-empty string")

        event = Event(name=event_name, data=data or {})
        handlers_called = 0

        with self._lock:
            # Exact matches
            exact_handlers = self._subscribers[event_name].copy()
            # Pattern matches
            pattern_handlers = []
            for pattern, handlers in self._pattern_subscribers.items():
                if PatternMatcher.matches(pattern, event_name):
                    pattern_handlers.extend(handlers)
            self._published_count += 1

        # Execute handlers outside lock (avoid deadlocks)
        for handler in exact_handlers + pattern_handlers:
            try:
                handler(event)
                handlers_called += 1
            except Exception as e:
                if error_handler:
                    error_handler(event_name, e)

        return handlers_called

    def unsubscribe_all(self, event_pattern: Optional[str] = None) -> int:
        """Clear all subscriptions, optionally for specific pattern."""
        with self._lock:
            if event_pattern:
                is_pattern = '*' in event_pattern
                subscribers = (self._pattern_subscribers[event_pattern]
                              if is_pattern else self._subscribers[event_pattern])
                count = len(subscribers)
                subscribers.clear()
            else:
                count = (sum(len(h) for h in self._subscribers.values()) +
                        sum(len(h) for h in self._pattern_subscribers.values()))
                self._subscribers.clear()
                self._pattern_subscribers.clear()
            return count

    def subscriber_count(self) -> int:
        """Total subscribers across all patterns."""
        with self._lock:
            return (sum(len(h) for h in self._subscribers.values()) +
                   sum(len(h) for h in self._pattern_subscribers.values()))


class Subscription:
    """Context manager for temporary subscriptions."""

    def __init__(self, bus: EventBus, pattern: str, handler: Callable):
        self.bus = bus
        self.pattern = pattern
        self.handler = handler

    def unsubscribe(self) -> bool:
        return self.bus.unsubscribe(self.pattern, self.handler)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.unsubscribe()

bus = EventBus()

# Exact subscription
bus.subscribe("pipeline.completed", lambda e: print(f"Done: {e.data}"))

# Wildcard
bus.subscribe("pipeline.*", lambda e: log_event(e.name))

# Error handling
bus.publish("batch.processed", 
    {"count": 1000},
    error_handler=lambda name, exc: logger.error(f"{name}: {exc}"))

# Once
bus.subscribe("startup.init", handler, once=True)

# Temporary
with bus.subscribe("temp_task", handler):
    do_work()  # Auto-unsubscribes on exit