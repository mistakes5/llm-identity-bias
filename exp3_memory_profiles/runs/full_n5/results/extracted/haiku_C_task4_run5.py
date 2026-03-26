"""
Thread-safe publish-subscribe event system with wildcard support.

Features:
- Subscribe to events with callback handlers
- Publish events with arbitrary data
- Unsubscribe from events
- Wildcard pattern matching (e.g., "user.*" matches "user.created", "user.updated")
- Support for both sync and async handlers
- Thread-safe using locks
"""

import asyncio
import uuid
from collections import defaultdict
from fnmatch import fnmatch
from threading import Lock
from typing import Any, Callable, Dict, List, Optional


class EventBus:
    """
    Central event bus for publish-subscribe messaging.

    Thread-safe event emitter supporting:
    - Direct event subscriptions
    - Wildcard pattern subscriptions
    - Sync and async handlers
    - Subscription management
    """

    def __init__(self):
        """Initialize the event bus."""
        self._handlers: Dict[str, List[tuple]] = defaultdict(list)
        self._wildcard_handlers: Dict[str, List[tuple]] = defaultdict(list)
        self._subscriptions: Dict[str, tuple] = {}
        self._lock = Lock()

    def subscribe(
        self,
        event: str,
        handler: Callable[[str, Any], Any],
        use_wildcard: bool = False
    ) -> str:
        """
        Subscribe to an event.

        Args:
            event: Event name or wildcard pattern (e.g., "user.created" or "user.*")
            handler: Callable that receives (event_name, data) as arguments.
                    Can be sync or async function.
            use_wildcard: If True, treat event as a fnmatch pattern.

        Returns:
            Subscription ID for later unsubscription
        """
        sub_id = str(uuid.uuid4())
        is_async = asyncio.iscoroutinefunction(handler)

        with self._lock:
            if use_wildcard:
                self._wildcard_handlers[event].append((sub_id, handler, is_async))
            else:
                self._handlers[event].append((sub_id, handler, is_async))

            self._subscriptions[sub_id] = (event, handler, is_async, use_wildcard)

        return sub_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Unsubscribe from an event using the subscription ID.

        Returns:
            True if unsubscribed successfully, False if ID not found
        """
        with self._lock:
            if subscription_id not in self._subscriptions:
                return False

            event, _, _, use_wildcard = self._subscriptions[subscription_id]

            if use_wildcard:
                self._wildcard_handlers[event] = [
                    (sid, h, ia) for sid, h, ia in self._wildcard_handlers[event]
                    if sid != subscription_id
                ]
            else:
                self._handlers[event] = [
                    (sid, h, ia) for sid, h, ia in self._handlers[event]
                    if sid != subscription_id
                ]

            del self._subscriptions[subscription_id]

        return True

    def publish(self, event: str, data: Any = None) -> None:
        """
        Publish an event synchronously.

        All registered handlers (direct and wildcard) are called.
        Async handlers are scheduled as tasks but not awaited.

        Args:
            event: Event name
            data: Optional data to pass to handlers
        """
        handlers_to_call = []

        with self._lock:
            if event in self._handlers:
                handlers_to_call.extend(self._handlers[event])

            for pattern, pattern_handlers in self._wildcard_handlers.items():
                if fnmatch(event, pattern):
                    handlers_to_call.extend(pattern_handlers)

        for _, handler, is_async in handlers_to_call:
            try:
                if is_async:
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(handler(event, data))
                    except RuntimeError:
                        asyncio.run(handler(event, data))
                else:
                    handler(event, data)
            except Exception as e:
                print(f"Error in event handler for '{event}': {e}")

    async def publish_async(self, event: str, data: Any = None) -> None:
        """
        Publish an event asynchronously, awaiting all async handlers.

        Args:
            event: Event name
            data: Optional data to pass to handlers
        """
        handlers_to_call = []

        with self._lock:
            if event in self._handlers:
                handlers_to_call.extend(self._handlers[event])

            for pattern, pattern_handlers in self._wildcard_handlers.items():
                if fnmatch(event, pattern):
                    handlers_to_call.extend(pattern_handlers)

        tasks = []
        for _, handler, is_async in handlers_to_call:
            try:
                if is_async:
                    tasks.append(handler(event, data))
                else:
                    handler(event, data)
            except Exception as e:
                print(f"Error in event handler for '{event}': {e}")

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def get_subscription_count(self, event: Optional[str] = None) -> int:
        """Get the number of subscriptions (total or for a specific event)."""
        with self._lock:
            if event is None:
                return len(self._subscriptions)

            count = len(self._handlers.get(event, []))

            for pattern, handlers_list in self._wildcard_handlers.items():
                if fnmatch(event, pattern):
                    count += len(handlers_list)

            return count

    def clear(self) -> None:
        """Clear all subscriptions and handlers."""
        with self._lock:
            self._handlers.clear()
            self._wildcard_handlers.clear()
            self._subscriptions.clear()

# test_event_bus.py
from event_bus import EventBus


def test_basic_subscription():
    """Test basic event subscription and publishing."""
    bus = EventBus()
    events = []

    def on_user_created(event_name: str, data: dict):
        events.append((event_name, data))

    sub_id = bus.subscribe("user.created", on_user_created)
    
    bus.publish("user.created", {"id": 1, "name": "Alice"})
    
    assert len(events) == 1
    assert events[0] == ("user.created", {"id": 1, "name": "Alice"})
    print("✓ Basic subscription test passed")


def test_unsubscribe():
    """Test unsubscribing from events."""
    bus = EventBus()
    events = []

    def handler(event_name: str, data: dict):
        events.append(event_name)

    sub_id = bus.subscribe("user.created", handler)
    bus.publish("user.created", {"id": 1})
    
    assert len(events) == 1
    
    # Unsubscribe
    assert bus.unsubscribe(sub_id) is True
    bus.publish("user.created", {"id": 2})
    
    # Should still have only 1 event
    assert len(events) == 1
    
    # Unsubscribing again should fail
    assert bus.unsubscribe(sub_id) is False
    print("✓ Unsubscribe test passed")


def test_wildcard_subscriptions():
    """Test wildcard pattern matching."""
    bus = EventBus()
    events = []

    def log_all(event_name: str, data: dict):
        events.append(event_name)

    # Subscribe to all user events
    bus.subscribe("user.*", log_all, use_wildcard=True)

    bus.publish("user.created", {"id": 1})
    bus.publish("user.updated", {"id": 1, "name": "Bob"})
    bus.publish("user.deleted", {"id": 1})
    bus.publish("post.created", {"id": 100})  # Should not match

    assert len(events) == 3
    assert events == ["user.created", "user.updated", "user.deleted"]
    print("✓ Wildcard subscription test passed")


def test_multiple_handlers():
    """Test multiple handlers for the same event."""
    bus = EventBus()
    results = []

    def handler1(event_name: str, data: dict):
        results.append(("h1", data["id"]))

    def handler2(event_name: str, data: dict):
        results.append(("h2", data["id"]))

    bus.subscribe("user.created", handler1)
    bus.subscribe("user.created", handler2)

    bus.publish("user.created", {"id": 42})

    assert len(results) == 2
    assert ("h1", 42) in results
    assert ("h2", 42) in results
    print("✓ Multiple handlers test passed")


def test_wildcard_patterns():
    """Test various wildcard patterns."""
    bus = EventBus()
    results = []

    def track(event_name: str, data: dict):
        results.append(event_name)

    # Subscribe to nested patterns
    bus.subscribe("*", track, use_wildcard=True)  # All events
    bus.publish("test", None)
    
    results.clear()
    bus.clear()
    
    # More specific wildcard
    bus.subscribe("db.*.success", track, use_wildcard=True)
    bus.publish("db.query.success", None)
    bus.publish("db.insert.success", None)
    bus.publish("db.query.error", None)  # Should not match

    assert len(results) == 2
    print("✓ Wildcard patterns test passed")


def test_async_handlers():
    """Test async handler support."""
    bus = EventBus()
    results = []

    async def async_handler(event_name: str, data: dict):
        await asyncio.sleep(0.01)
        results.append((event_name, data["id"]))

    bus.subscribe("user.created", async_handler)
    bus.publish("user.created", {"id": 1})

    # Give time for async handler to complete
    asyncio.run(asyncio.sleep(0.05))

    assert len(results) >= 1
    print("✓ Async handlers test passed")


async def test_publish_async():
    """Test async publishing with awaiting."""
    bus = EventBus()
    results = []

    async def slow_handler(event_name: str, data: dict):
        await asyncio.sleep(0.01)
        results.append(data["id"])

    bus.subscribe("task.complete", slow_handler)

    # publish_async waits for all handlers
    await bus.publish_async("task.complete", {"id": 1})
    await bus.publish_async("task.complete", {"id": 2})

    assert results == [1, 2]
    print("✓ Async publish test passed")


def test_subscription_count():
    """Test subscription counting."""
    bus = EventBus()

    def handler(event_name: str, data: dict):
        pass

    bus.subscribe("user.created", handler)
    bus.subscribe("user.created", handler)
    bus.subscribe("user.updated", handler)
    bus.subscribe("post.*", handler, use_wildcard=True)

    assert bus.get_subscription_count() == 4  # Total
    assert bus.get_subscription_count("user.created") == 2
    assert bus.get_subscription_count("user.updated") == 1
    print("✓ Subscription count test passed")


def test_error_handling():
    """Test that handler errors don't crash the bus."""
    bus = EventBus()
    results = []

    def bad_handler(event_name: str, data: dict):
        raise ValueError("Intentional error")

    def good_handler(event_name: str, data: dict):
        results.append("completed")

    bus.subscribe("test.event", bad_handler)
    bus.subscribe("test.event", good_handler)

    # Should not raise, should print error
    bus.publish("test.event", {})

    assert len(results) == 1  # Good handler still ran
    print("✓ Error handling test passed")


def run_all_tests():
    """Run all test cases."""
    print("Running EventBus Tests...\n")
    
    test_basic_subscription()
    test_unsubscribe()
    test_wildcard_subscriptions()
    test_multiple_handlers()
    test_wildcard_patterns()
    test_async_handlers()
    test_subscription_count()
    test_error_handling()
    
    asyncio.run(test_publish_async())
    
    print("\n✅ All tests passed!")


if __name__ == "__main__":
    run_all_tests()