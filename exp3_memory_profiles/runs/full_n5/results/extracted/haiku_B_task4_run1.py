"""
Publish-Subscribe Event System

A flexible event dispatcher supporting:
- Direct event subscriptions
- Wildcard pattern matching
- Thread-safe operations
- Exception handling
"""

import re
from typing import Callable, Any, Dict, List, Optional
from threading import RLock
from functools import wraps
from collections import defaultdict


class PubSub:
    """
    Thread-safe publish-subscribe event system with wildcard support.

    Example:
        pubsub = PubSub()

        # Direct subscription
        pubsub.subscribe('user.login', lambda data, event: print(f"User logged in: {data['id']}"))

        # Wildcard subscription
        pubsub.subscribe('user.*', lambda data, event: print(f"User event: {data}"))

        # Publish
        pubsub.publish('user.login', {'id': 123, 'username': 'alice'})
    """

    def __init__(self):
        """Initialize the PubSub system."""
        self._lock = RLock()

        # Store exact-match subscribers: event_name -> [callbacks]
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)

        # Store wildcard patterns: pattern -> (compiled_regex, [callbacks])
        self._wildcard_patterns: Dict[str, tuple] = {}

    def subscribe(
        self,
        event: str,
        callback: Callable,
        once: bool = False
    ) -> Callable:
        """
        Subscribe to an event with optional wildcard pattern matching.

        Args:
            event: Event name or wildcard pattern (e.g., 'user.login' or 'user.*')
            callback: Function to call when event is published. Signature: callback(data, event_name)
            once: If True, callback fires only once then auto-unsubscribes

        Returns:
            Unsubscribe function that removes this subscription

        Raises:
            TypeError: If callback is not callable
            ValueError: If event is empty string
        """
        if not callable(callback):
            raise TypeError(f"callback must be callable, got {type(callback)}")

        if not event:
            raise ValueError("event name cannot be empty")

        # Wrap callback if 'once' mode
        if once:
            original_callback = callback

            @wraps(original_callback)
            def once_wrapper(data, event_name):
                result = original_callback(data, event_name)
                unsubscribe()
                return result

            callback = once_wrapper

        with self._lock:
            is_wildcard = '*' in event

            if is_wildcard:
                regex_pattern = self._glob_to_regex(event)

                if event not in self._wildcard_patterns:
                    compiled_regex = re.compile(f"^{regex_pattern}$")
                    self._wildcard_patterns[event] = (compiled_regex, [])

                self._wildcard_patterns[event][1].append(callback)
            else:
                self._subscribers[event].append(callback)

        def unsubscribe():
            """Remove this subscription."""
            self.unsubscribe(event, callback)

        return unsubscribe

    def publish(self, event: str, data: Any = None) -> int:
        """
        Publish an event to all matching subscribers.

        Args:
            event: Event name to publish
            data: Optional data to pass to subscribers

        Returns:
            Number of callbacks executed

        Raises:
            RuntimeError: If any callback raises an exception
        """
        if not event:
            raise ValueError("event name cannot be empty")

        callbacks_to_run = []

        with self._lock:
            # Get exact-match subscribers
            callbacks_to_run.extend(self._subscribers.get(event, []))

            # Get wildcard subscribers that match this event
            for pattern, (regex, callbacks) in self._wildcard_patterns.items():
                if regex.match(event):
                    callbacks_to_run.extend(callbacks)

        # Execute callbacks (outside lock to prevent deadlocks)
        executed_count = 0
        exceptions = []

        for callback in callbacks_to_run:
            try:
                callback(data, event)
                executed_count += 1
            except Exception as e:
                exceptions.append((callback, e))

        # Report all exceptions after executing all callbacks
        if exceptions:
            error_msg = f"Errors in {len(exceptions)} callback(s):\n"
            for callback, exc in exceptions:
                error_msg += f"  - {callback.__name__}: {type(exc).__name__}: {exc}\n"
            raise RuntimeError(error_msg)

        return executed_count

    def unsubscribe(self, event: str, callback: Callable) -> bool:
        """
        Unsubscribe a specific callback from an event.

        Args:
            event: Event name or wildcard pattern
            callback: The callback function to remove

        Returns:
            True if callback was found and removed, False otherwise
        """
        with self._lock:
            is_wildcard = '*' in event
            found = False

            if is_wildcard:
                if event in self._wildcard_patterns:
                    callbacks = self._wildcard_patterns[event][1]
                    if callback in callbacks:
                        callbacks.remove(callback)
                        found = True
                        if not callbacks:
                            del self._wildcard_patterns[event]
            else:
                if event in self._subscribers:
                    callbacks = self._subscribers[event]
                    if callback in callbacks:
                        callbacks.remove(callback)
                        found = True
                        if not callbacks:
                            del self._subscribers[event]

            return found

    def unsubscribe_all(self, event: str) -> int:
        """
        Remove all subscribers from a specific event.

        Args:
            event: Event name or wildcard pattern

        Returns:
            Number of subscribers removed
        """
        with self._lock:
            is_wildcard = '*' in event
            count = 0

            if is_wildcard:
                if event in self._wildcard_patterns:
                    count = len(self._wildcard_patterns[event][1])
                    del self._wildcard_patterns[event]
            else:
                if event in self._subscribers:
                    count = len(self._subscribers[event])
                    del self._subscribers[event]

            return count

    def subscribers_count(self, event: Optional[str] = None) -> int:
        """
        Get count of subscribers.

        Args:
            event: If provided, count subscribers for this event only.
                   If None, count all subscribers.

        Returns:
            Number of subscribers
        """
        with self._lock:
            if event is None:
                exact_count = sum(len(cbs) for cbs in self._subscribers.values())
                wildcard_count = sum(len(cbs[1]) for cbs in self._wildcard_patterns.values())
                return exact_count + wildcard_count

            is_wildcard = '*' in event

            if is_wildcard:
                return len(self._wildcard_patterns.get(event, (None, []))[1])
            else:
                return len(self._subscribers.get(event, []))

    def clear(self) -> int:
        """Remove all subscribers from all events."""
        with self._lock:
            count = self.subscribers_count()
            self._subscribers.clear()
            self._wildcard_patterns.clear()
            return count

    @staticmethod
    def _glob_to_regex(pattern: str) -> str:
        """Convert glob pattern to regex."""
        escaped = re.escape(pattern)
        regex = escaped.replace(r'\*', '.*')
        return regex

    def list_subscriptions(self) -> Dict[str, List[str]]:
        """List all subscriptions (for debugging)."""
        with self._lock:
            result = {}

            for event, callbacks in self._subscribers.items():
                result[event] = [getattr(cb, '__name__', repr(cb)) for cb in callbacks]

            for pattern, (_, callbacks) in self._wildcard_patterns.items():
                result[pattern] = [getattr(cb, '__name__', repr(cb)) for cb in callbacks]

            return result


def event_handler(pubsub: PubSub, event_name: str, once: bool = False):
    """Decorator to register a function as an event handler."""
    def decorator(func):
        pubsub.subscribe(event_name, func, once=once)
        return func
    return decorator

"""Test suite and examples for the PubSub system."""

def test_basic_subscribe_publish():
    """Test basic subscription and publishing."""
    pubsub = PubSub()
    results = []

    def handler(data, event):
        results.append((event, data))

    pubsub.subscribe('user.login', handler)
    pubsub.publish('user.login', {'id': 1, 'name': 'Alice'})

    assert len(results) == 1
    assert results[0] == ('user.login', {'id': 1, 'name': 'Alice'})
    print("✓ Basic subscribe/publish works")


def test_unsubscribe():
    """Test unsubscribe functionality."""
    pubsub = PubSub()
    results = []

    def handler(data, event):
        results.append(data)

    unsub = pubsub.subscribe('event.test', handler)
    pubsub.publish('event.test', 'first')
    
    unsub()  # Unsubscribe using returned function
    
    pubsub.publish('event.test', 'second')

    assert len(results) == 1
    assert results[0] == 'first'
    print("✓ Unsubscribe works")


def test_wildcard_single_asterisk():
    """Test wildcard patterns like 'user.*'."""
    pubsub = PubSub()
    results = []

    def handler(data, event):
        results.append(event)

    pubsub.subscribe('user.*', handler)
    
    pubsub.publish('user.login', {'id': 1})
    pubsub.publish('user.logout', {'id': 1})
    pubsub.publish('user.profile.update', {'id': 1})
    pubsub.publish('admin.login', {'id': 2})  # Should NOT match

    assert results == ['user.login', 'user.logout', 'user.profile.update']
    print("✓ Wildcard 'user.*' works")


def test_wildcard_leading_asterisk():
    """Test wildcard patterns like '*.login'."""
    pubsub = PubSub()
    results = []

    def handler(data, event):
        results.append(event)

    pubsub.subscribe('*.login', handler)
    
    pubsub.publish('user.login', {})
    pubsub.publish('admin.login', {})
    pubsub.publish('guest.login', {})
    pubsub.publish('user.logout', {})  # Should NOT match

    assert results == ['user.login', 'admin.login', 'guest.login']
    print("✓ Wildcard '*.login' works")


def test_wildcard_multiple_asterisks():
    """Test complex wildcard patterns."""
    pubsub = PubSub()
    results = []

    def handler(data, event):
        results.append(event)

    pubsub.subscribe('user.*.update', handler)
    
    pubsub.publish('user.profile.update', {})
    pubsub.publish('user.settings.update', {})
    pubsub.publish('user.profile.delete', {})  # Should NOT match
    pubsub.publish('user.update', {})  # Should NOT match

    assert results == ['user.profile.update', 'user.settings.update']
    print("✓ Wildcard 'user.*.update' works")


def test_multiple_subscribers():
    """Test multiple subscribers to same event."""
    pubsub = PubSub()
    results = []

    def handler1(data, event):
        results.append(f"handler1: {data}")

    def handler2(data, event):
        results.append(f"handler2: {data}")

    pubsub.subscribe('event', handler1)
    pubsub.subscribe('event', handler2)
    
    pubsub.publish('event', 'data')

    assert len(results) == 2
    assert 'handler1: data' in results
    assert 'handler2: data' in results
    print("✓ Multiple subscribers work")


def test_once_subscription():
    """Test 'once' parameter for one-time subscriptions."""
    pubsub = PubSub()
    results = []

    def handler(data, event):
        results.append(data)

    pubsub.subscribe('event', handler, once=True)
    
    pubsub.publish('event', 'first')
    pubsub.publish('event', 'second')

    assert results == ['first']
    print("✓ 'once=True' subscription works")


def test_both_exact_and_wildcard():
    """Test that both exact and wildcard subscribers are called."""
    pubsub = PubSub()
    results = []

    def exact_handler(data, event):
        results.append(f"exact: {event}")

    def wildcard_handler(data, event):
        results.append(f"wildcard: {event}")

    pubsub.subscribe('user.login', exact_handler)
    pubsub.subscribe('user.*', wildcard_handler)
    
    pubsub.publish('user.login', {})

    assert len(results) == 2
    assert 'exact: user.login' in results
    assert 'wildcard: user.login' in results
    print("✓ Both exact and wildcard subscribers are called")


def test_error_handling():
    """Test that errors in one callback don't affect others."""
    pubsub = PubSub()
    results = []

    def failing_handler(data, event):
        raise ValueError("Something went wrong")

    def working_handler(data, event):
        results.append('success')

    pubsub.subscribe('event', failing_handler)
    pubsub.subscribe('event', working_handler)
    
    try:
        pubsub.publish('event', {})
    except RuntimeError as e:
        assert 'ValueError' in str(e)
        assert len(results) == 1  # Second handler still executed
        print("✓ Error handling works (one error doesn't block others)")


def test_subscribers_count():
    """Test subscriber counting."""
    pubsub = PubSub()

    def handler1(data, event): pass
    def handler2(data, event): pass
    def handler3(data, event): pass

    pubsub.subscribe('user.login', handler1)
    pubsub.subscribe('user.login', handler2)
    pubsub.subscribe('user.*', handler3)

    assert pubsub.subscribers_count('user.login') == 2
    assert pubsub.subscribers_count('user.*') == 1
    assert pubsub.subscribers_count() == 3
    print("✓ Subscriber counting works")


def test_decorator():
    """Test the @event_handler decorator."""
    pubsub = PubSub()
    results = []

    @event_handler(pubsub, 'user.login')
    def on_login(data, event):
        results.append(data)

    pubsub.publish('user.login', {'id': 123})
    assert results == [{'id': 123}]
    print("✓ @event_handler decorator works")


def test_clear():
    """Test clearing all subscribers."""
    pubsub = PubSub()

    pubsub.subscribe('event1', lambda d, e: None)
    pubsub.subscribe('event2', lambda d, e: None)
    pubsub.subscribe('event.*', lambda d, e: None)

    count = pubsub.clear()
    
    assert count == 3
    assert pubsub.subscribers_count() == 0
    print("✓ Clear works")


# Real-world example: Event logger
class EventLogger:
    """Example: A simple event logger using PubSub."""
    
    def __init__(self):
        self.pubsub = PubSub()
        self.logs = []
        
        # Subscribe to all events
        self.pubsub.subscribe('*', self._log_event)
    
    def _log_event(self, data, event):
        log_entry = f"[{event}] {data}"
        self.logs.append(log_entry)
        print(f"  LOG: {log_entry}")
    
    def emit(self, event: str, data: Any = None):
        return self.pubsub.publish(event, data)


def example_event_logger():
    """Example of using PubSub for an event logger."""
    print("\n📝 Event Logger Example:")
    logger = EventLogger()
    
    logger.emit('app.start', {'version': '1.0.0'})
    logger.emit('user.login', {'user_id': 123, 'ip': '192.168.1.1'})
    logger.emit('database.query', {'table': 'users', 'duration_ms': 45})
    logger.emit('user.logout', {'user_id': 123})
    
    print(f"  Total logs: {len(logger.logs)}")


# Real-world example: Event bus for application
class ApplicationEventBus:
    """Example: Central event bus for an application."""
    
    def __init__(self):
        self.pubsub = PubSub()
    
    def on_user_action(self, action: str, callback: Callable):
        """Subscribe to user actions."""
        self.pubsub.subscribe(f'user.action.{action}', callback)
    
    def on_system_event(self, event_type: str, callback: Callable):
        """Subscribe to system events."""
        self.pubsub.subscribe(f'system.{event_type}', callback)
    
    def on_any_error(self, callback: Callable):
        """Subscribe to all errors."""
        self.pubsub.subscribe('error.*', callback)
    
    def emit_user_action(self, action: str, data: dict):
        self.pubsub.publish(f'user.action.{action}', data)
    
    def emit_system_event(self, event_type: str, data: dict):
        self.pubsub.publish(f'system.{event_type}', data)
    
    def emit_error(self, error_type: str, error_msg: str):
        self.pubsub.publish(f'error.{error_type}', {'message': error_msg})


def example_application_event_bus():
    """Example of using PubSub as an application event bus."""
    print("\n🚀 Application Event Bus Example:")
    
    bus = ApplicationEventBus()
    notifications = []
    
    # Subscribe to various events
    bus.on_user_action('login', 
        lambda d, e: notifications.append(f"User {d['username']} logged in"))
    
    bus.on_user_action('logout',
        lambda d, e: notifications.append(f"User {d['username']} logged out"))
    
    bus.on_system_event('startup',
        lambda d, e: notifications.append(f"System started: {d['version']}"))
    
    bus.on_any_error('database',
        lambda d, e: notifications.append(f"DB Error: {d['message']}"))
    
    # Emit events
    bus.emit_system_event('startup', {'version': '2.1.0'})
    bus.emit_user_action('login', {'username': 'alice'})
    bus.emit_user_action('login', {'username': 'bob'})
    bus.emit_error('database', 'Connection timeout')
    bus.emit_user_action('logout', {'username': 'alice'})
    
    for notification in notifications:
        print(f"  📢 {notification}")


if __name__ == '__main__':
    print("🧪 Running PubSub Tests\n")
    
    test_basic_subscribe_publish()
    test_unsubscribe()
    test_wildcard_single_asterisk()
    test_wildcard_leading_asterisk()
    test_wildcard_multiple_asterisks()
    test_multiple_subscribers()
    test_once_subscription()
    test_both_exact_and_wildcard()
    test_error_handling()
    test_subscribers_count()
    test_decorator()
    test_clear()
    
    example_event_logger()
    example_application_event_bus()
    
    print("\n✅ All tests passed!")

# Basic usage
pubsub = PubSub()

# Direct subscription
pubsub.subscribe('user.login', lambda data, event: print(f"User logged in: {data['id']}"))

# Wildcard subscription
pubsub.subscribe('user.*', lambda data, event: print(f"User event: {event}"))

# Publish event
pubsub.publish('user.login', {'id': 123, 'username': 'alice'})

# Unsubscribe using returned function
unsub = pubsub.subscribe('order.created', handler)
unsub()  # Removes the subscription

# One-time subscription
pubsub.subscribe('app.shutdown', handler, once=True)

# Check subscription count
print(pubsub.subscribers_count())  # Total subscribers
print(pubsub.subscribers_count('user.login'))  # For specific event