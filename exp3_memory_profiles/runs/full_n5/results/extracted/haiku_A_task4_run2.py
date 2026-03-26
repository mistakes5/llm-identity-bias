"""
Publish-Subscribe Event System
A flexible, thread-safe event emitter supporting exact and wildcard subscriptions.
"""

import asyncio
import re
import threading
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Pattern, Union
import time


@dataclass
class Event:
    """Encapsulates event data with metadata."""
    name: str
    data: Any = None
    timestamp: float = field(default_factory=time.time)

    def __repr__(self) -> str:
        return f"Event(name={self.name!r}, data={self.data!r})"


class Handler(ABC):
    """Abstract base for event handlers (sync and async)."""

    @abstractmethod
    async def execute(self, event: Event) -> None:
        pass


class SyncHandler(Handler):
    """Wraps synchronous callable handlers."""

    def __init__(self, callback: Callable[[Event], None], name: Optional[str] = None):
        self.callback = callback
        self.name = name or callback.__name__

    async def execute(self, event: Event) -> None:
        self.callback(event)


class AsyncHandler(Handler):
    """Wraps asynchronous callable handlers."""

    def __init__(self, callback: Callable[[Event], Any], name: Optional[str] = None):
        self.callback = callback
        self.name = name or callback.__name__

    async def execute(self, event: Event) -> None:
        await self.callback(event)


class PatternMatcher(ABC):
    """Abstract base for event name pattern matching strategies."""

    @abstractmethod
    def matches(self, pattern: str, event_name: str) -> bool:
        pass


class PrefixWildcardMatcher(PatternMatcher):
    """
    Simple prefix-based wildcard matching.
    Examples: 'user.*' matches 'user.login', 'user.logout'
    """

    def matches(self, pattern: str, event_name: str) -> bool:
        if pattern == "*":
            return True
        if "*" not in pattern:
            return pattern == event_name
        
        prefix = pattern.rstrip("*").rstrip(".")
        if prefix == "":
            return True
        return event_name.startswith(prefix + ".")


class RegexMatcher(PatternMatcher):
    """
    Regex-based wildcard matching (more flexible).
    """

    def __init__(self):
        self._pattern_cache: Dict[str, Pattern] = {}

    def matches(self, pattern: str, event_name: str) -> bool:
        if pattern == "*":
            return True
        if pattern == event_name:
            return True

        if pattern not in self._pattern_cache:
            regex_pattern = pattern.replace(".", r"\.").replace("*", ".*")
            self._pattern_cache[pattern] = re.compile(f"^{regex_pattern}$")

        return bool(self._pattern_cache[pattern].match(event_name))


class EventBus:
    """
    Thread-safe publish-subscribe event bus.
    
    Features:
    - Exact and wildcard event subscriptions
    - Sync and async handler support
    - Pattern-based event matching
    - Thread-safe with RLock
    - Configurable error handling
    """

    def __init__(self, pattern_matcher: Optional[PatternMatcher] = None,
                 error_handler: Optional[Callable[[Any, Exception, Handler], None]] = None):
        self._handlers: Dict[str, List[Handler]] = {}
        self._pattern_matcher = pattern_matcher or PrefixWildcardMatcher()
        self._error_handler = error_handler
        self._lock = threading.RLock()

    def subscribe(
        self,
        event_pattern: str,
        handler: Union[Callable[[Event], None], Callable[[Event], Any]],
        name: Optional[str] = None,
    ) -> Callable[[], None]:
        """
        Subscribe to events matching the pattern.
        Returns an unsubscribe function.
        """
        with self._lock:
            wrapper = (AsyncHandler(handler, name) if asyncio.iscoroutinefunction(handler)
                      else SyncHandler(handler, name))

            if event_pattern not in self._handlers:
                self._handlers[event_pattern] = []

            self._handlers[event_pattern].append(wrapper)

        def unsubscribe() -> None:
            self.unsubscribe(event_pattern, wrapper)

        return unsubscribe

    def unsubscribe(self, event_pattern: str, handler: Union[Handler, Callable]) -> bool:
        """Unsubscribe a handler from an event pattern."""
        with self._lock:
            if event_pattern not in self._handlers:
                return False

            handlers = self._handlers[event_pattern]
            initial_count = len(handlers)

            if isinstance(handler, Handler):
                handlers[:] = [h for h in handlers if h is not handler]
            else:
                handlers[:] = [
                    h for h in handlers
                    if not (isinstance(h, (SyncHandler, AsyncHandler)) and h.callback is handler)
                ]

            removed = len(handlers) < initial_count
            if not handlers:
                del self._handlers[event_pattern]

            return removed

    def publish(self, event_name: str, data: Any = None) -> None:
        """Publish an event synchronously."""
        event = Event(event_name, data)
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._dispatch_async(event))

    async def publish_async(self, event_name: str, data: Any = None) -> None:
        """Publish an event asynchronously."""
        event = Event(event_name, data)
        await self._dispatch_async(event)

    async def _dispatch_async(self, event: Event) -> None:
        """Dispatch event to all matching handlers."""
        with self._lock:
            handlers_to_call = []
            for pattern, handlers in self._handlers.items():
                if self._pattern_matcher.matches(pattern, event.name):
                    handlers_to_call.extend(handlers)

        tasks = [self._safe_execute(handler, event) for handler in handlers_to_call]
        await asyncio.gather(*tasks)

    async def _safe_execute(self, handler: Handler, event: Event) -> None:
        """Execute a handler and call error_handler on exception."""
        try:
            await handler.execute(event)
        except Exception as e:
            if self._error_handler:
                self._error_handler(event, e, handler)

    def get_subscriptions(self, event_pattern: Optional[str] = None) -> Dict[str, int]:
        """Get subscription counts for debugging."""
        with self._lock:
            if event_pattern is not None:
                return {event_pattern: len(self._handlers.get(event_pattern, []))}
            return {p: len(h) for p, h in self._handlers.items()}

    def clear(self) -> None:
        """Remove all subscriptions."""
        with self._lock:
            self._handlers.clear()

from event_system import EventBus, Event, PrefixWildcardMatcher, RegexMatcher


def test_basic_subscription():
    """Test basic subscribe and publish."""
    bus = EventBus()
    results = []

    def on_event(event: Event):
        results.append(event.data)

    bus.subscribe('user.login', on_event)
    bus.publish('user.login', {'user': 'alice', 'timestamp': 1234})

    assert results == [{'user': 'alice', 'timestamp': 1234}]
    print("✓ Basic subscription works")


def test_wildcard_subscriptions():
    """Test wildcard pattern matching."""
    bus = EventBus()
    results = []

    def on_user_event(event: Event):
        results.append(event.name)

    # Subscribe to all user.* events
    bus.subscribe('user.*', on_user_event)

    bus.publish('user.login', None)
    bus.publish('user.logout', None)
    bus.publish('user.created', None)
    bus.publish('profile.update', None)  # Should not match

    assert results == ['user.login', 'user.logout', 'user.created']
    print("✓ Wildcard subscriptions work")


def test_unsubscribe():
    """Test unsubscribe functionality."""
    bus = EventBus()
    results = []

    def handler(event: Event):
        results.append(event.data)

    unsub = bus.subscribe('test.event', handler)
    bus.publish('test.event', 'first')

    unsub()  # Unsubscribe
    bus.publish('test.event', 'second')

    assert results == ['first']
    print("✓ Unsubscribe works")


def test_multiple_handlers():
    """Test multiple handlers on same event."""
    bus = EventBus()
    results = []

    def handler1(event: Event):
        results.append(('handler1', event.data))

    def handler2(event: Event):
        results.append(('handler2', event.data))

    bus.subscribe('event', handler1)
    bus.subscribe('event', handler2)
    bus.publish('event', 'data')

    # Order may vary due to concurrent execution
    assert len(results) == 2
    assert ('handler1', 'data') in results
    assert ('handler2', 'data') in results
    print("✓ Multiple handlers work")


async def test_async_handlers():
    """Test async handler support."""
    bus = EventBus()
    results = []

    async def async_handler(event: Event):
        await asyncio.sleep(0.01)
        results.append(f"async: {event.data}")

    def sync_handler(event: Event):
        results.append(f"sync: {event.data}")

    bus.subscribe('mixed.event', async_handler)
    bus.subscribe('mixed.event', sync_handler)

    await bus.publish_async('mixed.event', 'test')

    assert len(results) == 2
    assert "async: test" in results
    assert "sync: test" in results
    print("✓ Async handlers work")


def test_error_handling():
    """Test exception handling in handlers."""
    errors = []

    def error_handler(event, exception, handler):
        errors.append((event.name, str(exception)))

    bus = EventBus(error_handler=error_handler)

    def failing_handler(event: Event):
        raise ValueError("Handler failed!")

    def working_handler(event: Event):
        pass

    bus.subscribe('event', failing_handler)
    bus.subscribe('event', working_handler)

    bus.publish('event', None)

    assert len(errors) == 1
    assert errors[0][0] == 'event'
    assert "Handler failed!" in errors[0][1]
    print("✓ Error handling works")


def test_regex_matcher():
    """Test regex-based pattern matching."""
    bus = EventBus(pattern_matcher=RegexMatcher())
    results = []

    def handler(event: Event):
        results.append(event.name)

    # Regex patterns are more flexible
    bus.subscribe('user\\..*\\.login', handler)  # user.*.login pattern

    bus.publish('user.admin.login', None)
    bus.publish('user.guest.login', None)
    bus.publish('user.login', None)  # Should not match

    assert 'user.admin.login' in results
    assert 'user.guest.login' in results
    assert 'user.login' not in results
    print("✓ Regex matcher works")


def test_global_wildcard():
    """Test global wildcard subscription."""
    bus = EventBus()
    results = []

    def catch_all(event: Event):
        results.append(event.name)

    bus.subscribe('*', catch_all)

    bus.publish('event1', None)
    bus.publish('event2', None)
    bus.publish('user.login', None)

    assert len(results) == 3
    print("✓ Global wildcard works")


async def main():
    """Run all tests."""
    test_basic_subscription()
    test_wildcard_subscriptions()
    test_unsubscribe()
    test_multiple_handlers()
    await test_async_handlers()
    test_error_handling()
    test_regex_matcher()
    test_global_wildcard()

    print("\n✅ All tests passed!")


if __name__ == '__main__':
    asyncio.run(main())