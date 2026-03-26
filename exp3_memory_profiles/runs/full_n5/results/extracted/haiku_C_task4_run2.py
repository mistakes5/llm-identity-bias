"""
Publish-Subscribe Event System with Wildcard Support

A thread-safe event bus supporting:
- Direct event subscriptions
- Wildcard subscriptions (e.g., "user.*")
- Sync and async handlers
- One-time subscriptions
- Error handling and recovery
"""

import asyncio
import threading
from typing import Callable, Any, Dict, List, Optional
from dataclasses import dataclass
from fnmatch import fnmatch
from collections import defaultdict
import uuid


@dataclass
class Event:
    """Represents a published event."""
    name: str
    data: Any = None

    def __repr__(self) -> str:
        return f"Event(name={self.name!r}, data={self.data!r})"


class EventBus:
    """
    Thread-safe publish-subscribe event bus with wildcard support.

    Example:
        bus = EventBus()

        # Direct subscription
        @bus.on("user.created")
        def on_user_created(event: Event):
            print(f"User created: {event.data}")

        # Wildcard subscription
        @bus.on("user.*")
        def on_user_event(event: Event):
            print(f"User event: {event.name}")

        # Publish
        bus.publish("user.created", {"id": 123, "name": "Alice"})
    """

    def __init__(self):
        """Initialize the event bus."""
        self._direct_handlers: Dict[str, List[tuple]] = defaultdict(list)
        self._wildcard_handlers: List[tuple] = []
        self._lock = threading.RLock()

    def on(
        self,
        event_pattern: str,
        handler: Optional[Callable[[Event], Any]] = None,
        once: bool = False
    ) -> Optional[Callable]:
        """
        Subscribe to an event pattern.

        Args:
            event_pattern: Event name or wildcard pattern (e.g., "user.*")
            handler: Optional handler function. If None, returns a decorator.
            once: If True, handler fires only on first matching event.

        Returns:
            Subscription ID if handler is provided, else a decorator.
        """
        def decorator(fn: Callable) -> str:
            return self._subscribe(event_pattern, fn, once)

        if handler is None:
            return decorator
        else:
            return self._subscribe(event_pattern, handler, once)

    def once(self, event_pattern: str, handler: Optional[Callable[[Event], Any]] = None):
        """Subscribe to an event pattern, fires only once."""
        return self.on(event_pattern, handler, once=True)

    def _subscribe(self, event_pattern: str, handler: Callable, once: bool = False) -> str:
        """Register a handler for an event pattern."""
        if not callable(handler):
            raise TypeError(f"Handler must be callable, got {type(handler)}")

        subscription_id = str(uuid.uuid4())

        with self._lock:
            if self._is_wildcard(event_pattern):
                self._wildcard_handlers.append((event_pattern, subscription_id, handler, once))
            else:
                self._direct_handlers[event_pattern].append((subscription_id, handler, once))

        return subscription_id

    def off(self, subscription_id: str) -> bool:
        """
        Unsubscribe a handler by subscription ID.

        Returns:
            True if subscription was found and removed, False otherwise.
        """
        with self._lock:
            # Check direct handlers
            for event_name, handlers in list(self._direct_handlers.items()):
                original_len = len(handlers)
                self._direct_handlers[event_name] = [
                    (sid, handler, once) for sid, handler, once in handlers
                    if sid != subscription_id
                ]
                if len(self._direct_handlers[event_name]) < original_len:
                    if not self._direct_handlers[event_name]:
                        del self._direct_handlers[event_name]
                    return True

            # Check wildcard handlers
            original_len = len(self._wildcard_handlers)
            self._wildcard_handlers = [
                (pattern, sid, handler, once) for pattern, sid, handler, once in self._wildcard_handlers
                if sid != subscription_id
            ]
            return len(self._wildcard_handlers) < original_len

    def off_pattern(self, event_pattern: str) -> int:
        """Unsubscribe all handlers matching an event pattern."""
        count = 0
        with self._lock:
            if self._is_wildcard(event_pattern):
                original_len = len(self._wildcard_handlers)
                self._wildcard_handlers = [
                    (p, sid, h, once) for p, sid, h, once in self._wildcard_handlers
                    if p != event_pattern
                ]
                count = original_len - len(self._wildcard_handlers)
            else:
                if event_pattern in self._direct_handlers:
                    count = len(self._direct_handlers[event_pattern])
                    del self._direct_handlers[event_pattern]
        return count

    def publish(self, event_name: str, data: Any = None) -> None:
        """Publish an event synchronously to all matching subscribers."""
        event = Event(name=event_name, data=data)
        handlers = self._get_matching_handlers(event_name)

        for handler, once, subscription_id in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    self._run_async_handler(handler, event)
                else:
                    handler(event)
            except Exception as e:
                self._handle_error(event_name, handler, e)

            if once:
                self.off(subscription_id)

    async def publish_async(self, event_name: str, data: Any = None) -> None:
        """Publish an event asynchronously to all matching subscribers."""
        event = Event(name=event_name, data=data)
        handlers = self._get_matching_handlers(event_name)

        tasks = []
        for handler, once, subscription_id in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    tasks.append(handler(event))
                else:
                    handler(event)
            except Exception as e:
                self._handle_error(event_name, handler, e)

            if once:
                self.off(subscription_id)

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _get_matching_handlers(self, event_name: str) -> List[tuple]:
        """Get all handlers matching an event name (direct and wildcard)."""
        handlers = []

        with self._lock:
            # Direct matches
            if event_name in self._direct_handlers:
                handlers.extend([
                    (h, once, sid) for sid, h, once in self._direct_handlers[event_name]
                ])

            # Wildcard matches
            for pattern, subscription_id, handler, once in self._wildcard_handlers:
                if fnmatch(event_name, pattern):
                    handlers.append((handler, once, subscription_id))

        return handlers

    @staticmethod
    def _is_wildcard(pattern: str) -> bool:
        """Check if a pattern contains wildcard characters."""
        return any(c in pattern for c in ['*', '?', '[', ']'])

    def _run_async_handler(self, handler: Callable, event: Event) -> None:
        """Execute an async handler from a sync context."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(handler(event))
            else:
                loop.run_until_complete(handler(event))
        except RuntimeError:
            asyncio.run(handler(event))

    @staticmethod
    def _handle_error(event_name: str, handler: Callable, error: Exception) -> None:
        """Handle errors in event handlers."""
        handler_name = getattr(handler, '__name__', repr(handler))
        print(f"[EventBus Error] Event '{event_name}', handler '{handler_name}': {error}")

    def list_subscriptions(self, event_pattern: Optional[str] = None) -> Dict[str, int]:
        """Get a summary of subscriptions."""
        result = {}

        with self._lock:
            if event_pattern is None:
                for event_name, handlers in self._direct_handlers.items():
                    result[event_name] = len(handlers)
                for pattern, _, _, _ in self._wildcard_handlers:
                    result[pattern] = result.get(pattern, 0) + 1
            else:
                if self._is_wildcard(event_pattern):
                    count = sum(1 for p, _, _, _ in self._wildcard_handlers if p == event_pattern)
                    if count > 0:
                        result[event_pattern] = count
                else:
                    if event_pattern in self._direct_handlers:
                        result[event_pattern] = len(self._direct_handlers[event_pattern])

        return result

    def clear(self) -> None:
        """Remove all subscriptions."""
        with self._lock:
            self._direct_handlers.clear()
            self._wildcard_handlers.clear()

# ============================================================================
# EXAMPLE 1: Basic Pub/Sub
# ============================================================================
bus = EventBus()

@bus.on("user.created")
def on_user_created(event: Event):
    print(f"✓ User created: {event.data}")

bus.publish("user.created", {"id": 1, "name": "Alice"})
# Output: ✓ User created: {'id': 1, 'name': 'Alice'}


# ============================================================================
# EXAMPLE 2: Wildcard Subscriptions
# ============================================================================
bus = EventBus()

@bus.on("user.*")  # Matches: user.created, user.deleted, user.updated
def on_any_user_event(event: Event):
    print(f"♦ User event: {event.name}")

@bus.on("order.#")  # Matches: order.a, order.b, order.anything
def on_order_event(event: Event):
    print(f"○ Order event: {event.name}")

bus.publish("user.created", {})      # Matches: user.*
bus.publish("user.deleted", {})      # Matches: user.*
bus.publish("order.completed", {})   # Matches: order.#
bus.publish("payment.processed", {}) # No match


# ============================================================================
# EXAMPLE 3: Async Handlers
# ============================================================================
async def async_handler(event: Event):
    await asyncio.sleep(0.1)
    print(f"✓ Async: {event.name}")

bus = EventBus()
bus.on("task.started", async_handler)

# Option A: Run async from sync context
bus.publish("task.started", {"id": 123})

# Option B: Run fully async
asyncio.run(bus.publish_async("task.started", {"id": 123}))


# ============================================================================
# EXAMPLE 4: One-Time Subscriptions
# ============================================================================
bus = EventBus()
count = [0]

@bus.once("login")
def on_first_login(event: Event):
    count[0] += 1
    print(f"First login! Count: {count[0]}")

bus.publish("login", {})  # Prints "First login! Count: 1"
bus.publish("login", {})  # No output (already fired once)
print(count[0])           # Output: 1


# ============================================================================
# EXAMPLE 5: Subscription Management
# ============================================================================
bus = EventBus()

# Subscribe and get ID
sub_id = bus.on("data.changed", lambda e: print(f"Data: {e.data}"))

# Publish
bus.publish("data.changed", "v1")  # Prints "Data: v1"

# Unsubscribe by ID
bus.off(sub_id)
bus.publish("data.changed", "v2")  # No output

# Remove all subscriptions to a pattern
bus.on("user.*", lambda e: print(f"User: {e.name}"))
bus.on("user.*", lambda e: print(f"User2: {e.name}"))
removed = bus.off_pattern("user.*")
print(f"Removed {removed} handlers")


# ============================================================================
# EXAMPLE 6: Introspection
# ============================================================================
bus = EventBus()
bus.on("user.created", lambda e: None)
bus.on("user.*", lambda e: None)
bus.on("order.processed", lambda e: None)

# List all subscriptions
print(bus.list_subscriptions())
# Output: {'user.created': 1, 'user.*': 1, 'order.processed': 1}

# List specific pattern
print(bus.list_subscriptions("user.*"))
# Output: {'user.*': 1}


# ============================================================================
# EXAMPLE 7: Real-World Use Case - E-Commerce System
# ============================================================================
class OrderService:
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.bus.on("order.created", self.notify_warehouse)
        self.bus.on("order.*", self.log_event)

    def notify_warehouse(self, event: Event):
        print(f"📦 Warehouse: Prepare order {event.data['order_id']}")

    def log_event(self, event: Event):
        print(f"📝 Log: {event.name} - {event.data}")

class PaymentService:
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.bus.on("order.created", self.charge_customer)

    def charge_customer(self, event: Event):
        print(f"💳 Charging ${event.data['amount']} for order {event.data['order_id']}")

bus = EventBus()
order_service = OrderService(bus)
payment_service = PaymentService(bus)

# Create order
bus.publish("order.created", {
    "order_id": "ORD-001",
    "amount": 99.99,
    "customer": "Alice"
})

# Output:
# 💳 Charging $99.99 for order ORD-001
# 📦 Warehouse: Prepare order ORD-001
# 📝 Log: order.created - {'order_id': 'ORD-001', 'amount': 99.99, 'customer': 'Alice'}

import unittest

class TestEventBus(unittest.TestCase):
    def setUp(self):
        self.bus = EventBus()
        self.results = []

    def test_direct_subscription(self):
        """Test basic pub/sub."""
        @self.bus.on("test")
        def handler(event):
            self.results.append(event.data)

        self.bus.publish("test", "data")
        self.assertEqual(self.results, ["data"])

    def test_wildcard_subscription(self):
        """Test wildcard patterns."""
        @self.bus.on("user.*")
        def handler(event):
            self.results.append(event.name)

        self.bus.publish("user.created", {})
        self.bus.publish("user.deleted", {})
        self.bus.publish("admin.created", {})  # No match

        self.assertEqual(self.results, ["user.created", "user.deleted"])

    def test_unsubscribe(self):
        """Test subscription removal."""
        sub_id = self.bus.on("test", lambda e: self.results.append(1))
        self.bus.publish("test", None)
        self.bus.off(sub_id)
        self.bus.publish("test", None)
        self.assertEqual(self.results, [1])

    def test_once(self):
        """Test one-time subscriptions."""
        @self.bus.once("test")
        def handler(event):
            self.results.append(1)

        self.bus.publish("test", None)
        self.bus.publish("test", None)
        self.assertEqual(self.results, [1])

    def test_error_handling(self):
        """Test that errors in handlers don't crash the bus."""
        def bad_handler(event):
            raise ValueError("Intentional error")

        def good_handler(event):
            self.results.append("ok")

        self.bus.on("test", bad_handler)
        self.bus.on("test", good_handler)

        self.bus.publish("test", None)
        self.assertEqual(self.results, ["ok"])

if __name__ == "__main__":
    unittest.main()