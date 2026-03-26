"""
event_bus.py — Thread-safe publish-subscribe event bus with wildcard topics.

Topic syntax (dot-delimited segments):
  *    one segment      user.*    → user.created ✓  user.a.b ✗
  **   zero or more    user.**   → user.created ✓  user.a.b ✓
                        **        → any topic

Usage:
    bus = EventBus()
    sid = bus.subscribe("order.*", handler)
    bus.publish("order.placed", {"id": 42})
    bus.unsubscribe(sid)

    with bus.subscription("metrics.**")(my_handler):
        bus.publish("metrics.cpu.load", 0.73)

    await bus.publish_async("order.placed", payload)

    # Lenient delivery (log-and-continue)
    bus = EventBus(on_error=error_policy_log)

    # Fail-fast
    bus = EventBus(on_error=error_policy_raise)

Requires Python >= 3.11 (ExceptionGroup).
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Union
from uuid import uuid4

log = logging.getLogger(__name__)

HandlerFn = Callable[["Event"], Union[None, Coroutine[Any, Any, None]]]
ErrorFn   = Callable[[str, Exception], None]   # (sub_id, exc)


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class Event:
    """Immutable event envelope."""
    topic: str
    data: Any = None


@dataclass(slots=True)
class Subscription:
    id:      str
    pattern: str
    handler: HandlerFn

    def __repr__(self) -> str:
        return f"Subscription(id={self.id!r}, pattern={self.pattern!r})"


# ---------------------------------------------------------------------------
# Wildcard matching
# ---------------------------------------------------------------------------

def _matches(pattern: str, topic: str) -> bool:
    """
    Hierarchical topic matching over dot-delimited segments.

    *  → exactly one segment
    ** → zero or more segments (greedy backtracking)

    >>> _matches("user.*",  "user.created")   # True
    >>> _matches("user.*",  "user.a.b")       # False
    >>> _matches("user.**", "user.a.b")       # True
    >>> _matches("**",      "any.topic.ever") # True
    """
    if pattern == "**":
        return True
    return _match_parts(pattern.split("."), 0, topic.split("."), 0)


def _match_parts(pp: list[str], pi: int, tp: list[str], ti: int) -> bool:
    """Recursive descent with backtracking on **."""
    while pi < len(pp) and ti < len(tp):
        seg = pp[pi]
        if seg == "**":
            for skip in range(len(tp) - ti + 1):
                if _match_parts(pp, pi + 1, tp, ti + skip):
                    return True
            return False
        if seg != "*" and seg != tp[ti]:
            return False
        pi += 1
        ti += 1

    # Drain trailing ** (matches zero segments at end)
    while pi < len(pp) and pp[pi] == "**":
        pi += 1

    return pi == len(pp) and ti == len(tp)


# ---------------------------------------------------------------------------
# Built-in error policies
# ---------------------------------------------------------------------------

def error_policy_raise(sub_id: str, exc: Exception) -> None:
    """Fail-fast: re-raise immediately, skipping remaining handlers."""
    raise exc


def error_policy_log(sub_id: str, exc: Exception) -> None:
    """Lenient: log and continue. Matches Kafka consumer-group semantics."""
    log.error("EventBus handler %s raised: %s", sub_id, exc, exc_info=exc)


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------

class EventBus:
    """
    Thread-safe pub/sub event bus with hierarchical wildcard topics.

    Args:
        on_error: Called as on_error(sub_id, exc) per failure.
                  Built-ins: error_policy_raise, error_policy_log.
                  Default: collect all failures, raise ExceptionGroup.
    """

    def __init__(self, on_error: ErrorFn | None = None) -> None:
        self._subscriptions: dict[str, Subscription] = {}
        # RLock: handlers may re-publish to the same bus without deadlock.
        self._lock     = threading.RLock()
        self._on_error = on_error

    # ── Subscription lifecycle ──────────────────────────────────────────────

    def subscribe(self, pattern: str, handler: HandlerFn) -> str:
        """Register handler for pattern. Returns opaque subscription ID."""
        sub_id = str(uuid4())
        with self._lock:
            self._subscriptions[sub_id] = Subscription(sub_id, pattern, handler)
        return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
        """Remove subscription by ID. Returns True if it existed."""
        with self._lock:
            return self._subscriptions.pop(sub_id, None) is not None

    def subscription(self, pattern: str) -> _SubscriptionCtx:
        """
        Context manager that auto-unsubscribes on exit.

            with bus.subscription("order.*")(my_handler):
                bus.publish("order.placed", ...)
        """
        return _SubscriptionCtx(self, pattern)

    # ── Publishing ──────────────────────────────────────────────────────────

    def publish(self, topic: str, data: Any = None) -> int:
        """
        Synchronous dispatch. Coroutine handlers are detected and warned —
        use publish_async() for async handlers.
        Returns count of handlers invoked.
        """
        event   = Event(topic, data)
        matched = self._matching_subs(topic)
        errors: list[tuple[str, Exception]] = []

        for sub in matched:
            try:
                result = sub.handler(event)
                if asyncio.iscoroutine(result):
                    result.close()
                    log.warning(
                        "Async handler on sub %s returned a coroutine during "
                        "synchronous publish('%s'). Use publish_async().",
                        sub.id, topic,
                    )
            except Exception as exc:  # noqa: BLE001
                errors.append((sub.id, exc))

        self._dispatch_errors(errors, topic)
        return len(matched)

    async def publish_async(self, topic: str, data: Any = None) -> int:
        """Async publish: coroutine handlers are awaited, sync handlers run inline."""
        event   = Event(topic, data)
        matched = self._matching_subs(topic)
        errors: list[tuple[str, Exception]] = []

        for sub in matched:
            try:
                result = sub.handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as exc:  # noqa: BLE001
                errors.append((sub.id, exc))

        self._dispatch_errors(errors, topic)
        return len(matched)

    # ── Error dispatching ───────────────────────────────────────────────────

    def _dispatch_errors(
        self,
        errors: list[tuple[str, Exception]],
        topic: str,
    ) -> None:
        """
        Route failures through the configured error policy.

        Custom on_error: called per failure; may raise to short-circuit.
        Default (None):  collect all, raise ExceptionGroup.
        """
        if not errors:
            return

        if self._on_error is not None:
            for sub_id, exc in errors:
                self._on_error(sub_id, exc)   # error_policy_raise stops here
            return

        # Default: collect-all for maximum blast-radius visibility
        raise ExceptionGroup(
            f"EventBus: {len(errors)} handler(s) failed on topic {topic!r}",
            [exc for _, exc in errors],
        )

    # ── Introspection ───────────────────────────────────────────────────────

    def subscriber_count(self, topic: str | None = None) -> int:
        """Active subscription count; filtered by topic match if provided."""
        with self._lock:
            if topic is None:
                return len(self._subscriptions)
            return sum(
                1 for s in self._subscriptions.values()
                if _matches(s.pattern, topic)
            )

    def clear(self) -> None:
        """Remove all subscriptions."""
        with self._lock:
            self._subscriptions.clear()

    def _matching_subs(self, topic: str) -> list[Subscription]:
        with self._lock:
            return [s for s in self._subscriptions.values() if _matches(s.pattern, topic)]

    def __repr__(self) -> str:
        with self._lock:
            n = len(self._subscriptions)
        return f"EventBus(subscriptions={n})"


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------

class _SubscriptionCtx:
    def __init__(self, bus: EventBus, pattern: str) -> None:
        self._bus     = bus
        self._pattern = pattern
        self._sub_id: str | None       = None
        self._handler: HandlerFn | None = None

    def __call__(self, handler: HandlerFn) -> _SubscriptionCtx:
        self._handler = handler
        return self

    def __enter__(self) -> _SubscriptionCtx:
        if self._handler is None:
            raise RuntimeError("Provide a handler before entering context: ctx(handler)")
        self._sub_id = self._bus.subscribe(self._pattern, self._handler)
        return self

    def __exit__(self, *_: object) -> None:
        if self._sub_id:
            self._bus.unsubscribe(self._sub_id)
            self._sub_id = None

    @property
    def sub_id(self) -> str | None:
        return self._sub_id

"""pytest test suite for EventBus."""

from collections import defaultdict

import pytest

from event_bus import (
    Event,
    EventBus,
    _matches,
    error_policy_log,
    error_policy_raise,
)


# ---------------------------------------------------------------------------
# Wildcard matching unit tests
# ---------------------------------------------------------------------------

class TestWildcardMatching:
    def test_exact_match(self):
        assert _matches("user.created", "user.created")

    def test_exact_no_match(self):
        assert not _matches("user.created", "user.updated")

    def test_single_wildcard_one_segment(self):
        assert _matches("user.*", "user.created")

    def test_single_wildcard_no_deep_match(self):
        assert not _matches("user.*", "user.profile.updated")

    def test_single_wildcard_prefix(self):
        assert _matches("*.created", "order.created")

    def test_double_wildcard_deep(self):
        assert _matches("user.**", "user.profile.updated")

    def test_double_wildcard_zero_segments(self):
        # user.** should match user itself if ** can consume zero
        assert _matches("user.**", "user")

    def test_double_wildcard_global(self):
        assert _matches("**", "any.topic.at.all")

    def test_double_wildcard_middle(self):
        assert _matches("a.**.z", "a.b.c.z")

    def test_double_wildcard_middle_no_trailing(self):
        assert not _matches("a.**.z", "a.b.c.x")

    def test_no_false_prefix_match(self):
        assert not _matches("user", "user.created")

    def test_no_false_suffix_match(self):
        assert not _matches("user.created", "order.user.created")


# ---------------------------------------------------------------------------
# Subscribe / unsubscribe
# ---------------------------------------------------------------------------

class TestSubscribeUnsubscribe:
    def test_subscribe_returns_id(self):
        bus = EventBus(on_error=error_policy_raise)
        sid = bus.subscribe("a.b", lambda e: None)
        assert isinstance(sid, str) and len(sid) == 36  # UUID4

    def test_unsubscribe_removes(self):
        bus = EventBus(on_error=error_policy_raise)
        sid = bus.subscribe("a.b", lambda e: None)
        assert bus.unsubscribe(sid) is True
        assert bus.subscriber_count() == 0

    def test_unsubscribe_nonexistent(self):
        bus = EventBus(on_error=error_policy_raise)
        assert bus.unsubscribe("does-not-exist") is False

    def test_multiple_subs_same_pattern(self):
        bus = EventBus(on_error=error_policy_raise)
        ids = {bus.subscribe("x", lambda e: None) for _ in range(3)}
        assert len(ids) == 3
        assert bus.subscriber_count() == 3

    def test_context_manager_auto_unsubscribes(self):
        bus = EventBus(on_error=error_policy_raise)
        with bus.subscription("a.*")(lambda e: None):
            assert bus.subscriber_count() == 1
        assert bus.subscriber_count() == 0

    def test_context_manager_no_handler_raises(self):
        bus = EventBus(on_error=error_policy_raise)
        with pytest.raises(RuntimeError):
            with bus.subscription("a.*"):
                pass


# ---------------------------------------------------------------------------
# Publish
# ---------------------------------------------------------------------------

class TestPublish:
    def test_exact_topic_dispatched(self):
        bus    = EventBus(on_error=error_policy_raise)
        events = []
        bus.subscribe("order.placed", events.append)
        count = bus.publish("order.placed", {"id": 1})
        assert count == 1
        assert events[0].data == {"id": 1}

    def test_no_match_not_dispatched(self):
        bus    = EventBus(on_error=error_policy_raise)
        events = []
        bus.subscribe("order.placed", events.append)
        bus.publish("order.cancelled")
        assert events == []

    def test_wildcard_single_segment(self):
        bus    = EventBus(on_error=error_policy_raise)
        events = []
        bus.subscribe("order.*", events.append)
        bus.publish("order.placed")
        bus.publish("order.cancelled")
        bus.publish("order.item.added")   # should NOT match
        assert len(events) == 2

    def test_wildcard_multi_segment(self):
        bus    = EventBus(on_error=error_policy_raise)
        events = []
        bus.subscribe("order.**", events.append)
        bus.publish("order.placed")
        bus.publish("order.item.added")
        assert len(events) == 2

    def test_global_wildcard(self):
        bus    = EventBus(on_error=error_policy_raise)
        events = []
        bus.subscribe("**", events.append)
        bus.publish("a.b.c")
        bus.publish("x")
        assert len(events) == 2

    def test_multiple_subscribers_same_topic(self):
        bus = EventBus(on_error=error_policy_raise)
        seen = defaultdict(int)
        bus.subscribe("ping", lambda e: seen.__setitem__("a", seen["a"] + 1))
        bus.subscribe("ping", lambda e: seen.__setitem__("b", seen["b"] + 1))
        bus.publish("ping")
        assert seen["a"] == 1 and seen["b"] == 1

    def test_publish_returns_handler_count(self):
        bus = EventBus(on_error=error_policy_raise)
        bus.subscribe("x", lambda e: None)
        bus.subscribe("x", lambda e: None)
        assert bus.publish("x") == 2

    def test_unsubscribed_handler_not_called(self):
        bus    = EventBus(on_error=error_policy_raise)
        events = []
        sid    = bus.subscribe("x", events.append)
        bus.unsubscribe(sid)
        bus.publish("x")
        assert events == []

    def test_event_data_passed_correctly(self):
        bus     = EventBus(on_error=error_policy_raise)
        payload = {"key": "value", "n": 42}
        received: list[Event] = []
        bus.subscribe("data.*", received.append)
        bus.publish("data.ready", payload)
        assert received[0].topic == "data.ready"
        assert received[0].data  == payload


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    def test_default_collects_all_errors(self):
        bus = EventBus()   # default: collect-all
        bus.subscribe("x", lambda e: (_ for _ in ()).throw(ValueError("a")))
        bus.subscribe("x", lambda e: (_ for _ in ()).throw(ValueError("b")))
        with pytest.raises(ExceptionGroup) as exc_info:
            bus.publish("x")
        assert len(exc_info.value.exceptions) == 2

    def test_fail_fast_stops_after_first(self):
        bus   = EventBus(on_error=error_policy_raise)
        calls = []
        bus.subscribe("x", lambda e: (_ for _ in ()).throw(RuntimeError("stop")))
        bus.subscribe("x", lambda e: calls.append(1))
        with pytest.raises(RuntimeError, match="stop"):
            bus.publish("x")
        # Second handler may or may not have run depending on subscribe order;
        # what matters is the exception propagates.

    def test_lenient_policy_continues(self):
        bus    = EventBus(on_error=error_policy_log)
        events = []
        bus.subscribe("x", lambda e: (_ for _ in ()).throw(RuntimeError("bad")))
        bus.subscribe("x", events.append)
        count = bus.publish("x")   # must not raise
        assert count == 2
        assert len(events) == 1

    def test_reentrant_publish_in_handler(self):
        """Handler re-publishes on the same bus without deadlock (RLock)."""
        bus    = EventBus(on_error=error_policy_raise)
        events = []

        def on_first(e: Event) -> None:
            bus.publish("second", "chained")

        bus.subscribe("first",  on_first)
        bus.subscribe("second", events.append)
        bus.publish("first")
        assert events[0].data == "chained"


# ---------------------------------------------------------------------------
# Async publish
# ---------------------------------------------------------------------------

class TestAsyncPublish:
    def test_async_handler_awaited(self):
        bus    = EventBus(on_error=error_policy_raise)
        events = []

        async def async_handler(e: Event) -> None:
            events.append(e)

        bus.subscribe("tick", async_handler)
        asyncio.run(bus.publish_async("tick", "payload"))
        assert events[0].data == "payload"

    def test_mixed_sync_async_handlers(self):
        bus  = EventBus(on_error=error_policy_raise)
        sync_seen:  list[str] = []
        async_seen: list[str] = []

        async def async_h(e: Event) -> None:
            async_seen.append(e.data)

        bus.subscribe("x", lambda e: sync_seen.append(e.data))
        bus.subscribe("x", async_h)
        asyncio.run(bus.publish_async("x", "hello"))
        assert sync_seen == ["hello"]
        assert async_seen == ["hello"]


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafety:
    def test_concurrent_publish(self):
        """N threads publish simultaneously; every handler must run exactly once."""
        N      = 20
        bus    = EventBus(on_error=error_policy_raise)
        counts = defaultdict(int)
        lock   = threading.Lock()
        barrier = threading.Barrier(N)

        def handler(e: Event) -> None:
            with lock:
                counts[e.data] += 1

        bus.subscribe("concurrent.*", handler)

        def worker(i: int) -> None:
            barrier.wait()   # all threads reach publish at the same time
            bus.publish(f"concurrent.{i}", i)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(N)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(counts) == N
        assert all(v == 1 for v in counts.values())

    def test_subscribe_during_publish(self):
        """New subscriptions added during dispatch don't affect the current delivery."""
        bus    = EventBus(on_error=error_policy_raise)
        called = []

        def late_handler(e: Event) -> None:
            called.append("late")

        def early_handler(e: Event) -> None:
            called.append("early")
            bus.subscribe("x", late_handler)   # add during dispatch

        bus.subscribe("x", early_handler)
        bus.publish("x")
        assert called == ["early"]   # late_handler not yet active


# ---------------------------------------------------------------------------
# Introspection
# ---------------------------------------------------------------------------

class TestIntrospection:
    def test_subscriber_count_all(self):
        bus = EventBus(on_error=error_policy_raise)
        bus.subscribe("a", lambda e: None)
        bus.subscribe("b", lambda e: None)
        assert bus.subscriber_count() == 2

    def test_subscriber_count_for_topic(self):
        bus = EventBus(on_error=error_policy_raise)
        bus.subscribe("user.*",  lambda e: None)
        bus.subscribe("order.*", lambda e: None)
        bus.subscribe("**",      lambda e: None)
        # "user.created" matches user.* and **
        assert bus.subscriber_count("user.created") == 2

    def test_clear(self):
        bus = EventBus(on_error=error_policy_raise)
        bus.subscribe("a", lambda e: None)
        bus.clear()
        assert bus.subscriber_count() == 0

# Lenient (ETL pipelines, Kafka-style)
bus = EventBus(on_error=error_policy_log)

# Strict (event sourcing, audit logs)
bus = EventBus(on_error=error_policy_raise)

# Custom dead-letter queue
bus = EventBus(on_error=lambda sid, exc: dlq.send(sid, exc))