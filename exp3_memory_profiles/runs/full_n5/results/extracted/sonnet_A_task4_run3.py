"""
pubsub.py — Thread-safe publish-subscribe event bus with wildcard patterns.

Event names use dot-separated segments:  "user.created", "order.item.shipped"

Wildcard syntax:
    *   — matches exactly one segment    ("user.*"  matches "user.login")
    **  — matches one or more segments   ("order.**" matches "order.item.shipped")
"""

from __future__ import annotations

import re
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Optional
from uuid import uuid4


# ─── Data types ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Subscription:
    id: str
    pattern: str
    handler: Callable[[str, Any], Any]


@dataclass
class PublishResult:
    """
    Outcome of a single publish() call.

    Attributes:
        event    — The published event name.
        results  — Return values from each successfully called handler.
        errors   — (subscription_id, exception) pairs for any handler that raised.
    """
    event: str
    results: list[Any] = field(default_factory=list)
    errors: list[tuple[str, Exception]] = field(default_factory=list)

    @property
    def succeeded(self) -> bool:
        return len(self.errors) == 0

    def raise_errors(self) -> None:
        """Re-raise the first handler error, if any."""
        if self.errors:
            _, exc = self.errors[0]
            raise exc


# ─── Core EventBus ──────────────────────────────────────────────────────────

class EventBus:
    """
    Thread-safe publish-subscribe event bus.

    Parameters:
        error_handler — Optional callable(subscription_id, exception) invoked
                        on handler errors. Useful for logging. Must not raise.
    """

    def __init__(
        self,
        error_handler: Optional[Callable[[str, Exception], None]] = None,
    ) -> None:
        self._subscriptions: dict[str, Subscription] = {}
        self._pattern_cache: dict[str, re.Pattern[str]] = {}
        self._lock = threading.RLock()   # RLock allows re-entrant publish() from handlers
        self._error_handler = error_handler

    # ── Subscription management ──────────────────────────────────────────

    def subscribe(self, pattern: str, handler: Callable[[str, Any], Any]) -> str:
        """Subscribe handler to pattern. Returns a subscription ID."""
        sub_id = str(uuid4())
        with self._lock:
            self._subscriptions[sub_id] = Subscription(id=sub_id, pattern=pattern, handler=handler)
            if pattern not in self._pattern_cache:
                self._pattern_cache[pattern] = self._compile_pattern(pattern)
        return sub_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove a subscription. Returns True if it existed, False otherwise."""
        with self._lock:
            if subscription_id in self._subscriptions:
                del self._subscriptions[subscription_id]
                return True
            return False

    def on(self, pattern: str) -> Callable:
        """
        Decorator that subscribes a function for its lifetime.

            @bus.on("user.*")
            def handle_user(event: str, data) -> None: ...
        """
        def decorator(fn: Callable) -> Callable:
            self.subscribe(pattern, fn)
            return fn
        return decorator

    @contextmanager
    def subscription(self, pattern: str, handler: Callable) -> Iterator[str]:
        """
        Context manager that auto-unsubscribes on exit.

            with bus.subscription("user.*", handler) as sub_id:
                bus.publish("user.login", {...})
            # handler is no longer active here
        """
        sub_id = self.subscribe(pattern, handler)
        try:
            yield sub_id
        finally:
            self.unsubscribe(sub_id)

    # ── Publishing ───────────────────────────────────────────────────────

    def publish(self, event: str, data: Any = None) -> PublishResult:
        """
        Publish event with optional data to all matching subscribers.
        Handler errors are isolated via _handle_publish_error().
        """
        with self._lock:
            matching = [
                sub for sub in self._subscriptions.values()
                if self._matches(sub.pattern, event)
            ]

        result = PublishResult(event=event)
        for sub in matching:
            try:
                value = sub.handler(event, data)
                result.results.append(value)
            except Exception as exc:
                self._handle_publish_error(sub.id, exc, result)

        return result

    def _handle_publish_error(
        self,
        subscription_id: str,
        exc: Exception,
        result: PublishResult,
    ) -> None:
        """
        TODO — implement your preferred error isolation strategy here (~5 lines).

        Called whenever a subscriber handler raises. Choose your trade-off:

        Option A — Collect and continue (all other handlers still run):
            result.errors.append((subscription_id, exc))
            if self._error_handler:
                self._error_handler(subscription_id, exc)

        Option B — Fail-fast (strict contract, stops on first error):
            raise exc

        Option C — Swallow silently (fire-and-forget, zero visibility):
            pass

        Option D — Delegate to error_handler, always surface in result:
            result.errors.append((subscription_id, exc))
            if self._error_handler:
                try:
                    self._error_handler(subscription_id, exc)
                except Exception:
                    pass  # never let the error handler break the bus
        """
        raise NotImplementedError(
            "Implement _handle_publish_error() to define your error strategy."
        )

    # ── Introspection ─────────────────────────────────────────────────────

    def subscriber_count(self, event: Optional[str] = None) -> int:
        """Count active subscriptions, optionally filtered by matching event."""
        with self._lock:
            if event is None:
                return len(self._subscriptions)
            return sum(1 for sub in self._subscriptions.values()
                       if self._matches(sub.pattern, event))

    def patterns(self) -> list[str]:
        """Return all active subscription patterns."""
        with self._lock:
            return [sub.pattern for sub in self._subscriptions.values()]

    def clear(self) -> None:
        """Remove all subscriptions and the compiled pattern cache."""
        with self._lock:
            self._subscriptions.clear()
            self._pattern_cache.clear()

    # ── Pattern matching ──────────────────────────────────────────────────

    @staticmethod
    def _compile_pattern(pattern: str) -> re.Pattern[str]:
        """
        Convert a wildcard pattern to a compiled regex.

        re.split with a capturing group keeps the delimiters in the result,
        so ** is handled before * in one pass — no partial overlap possible.

            **  ->  [^.]+(?:\\.[^.]+)*   (one or more dot-separated segments)
            *   ->  [^.]+                 (exactly one segment, no dot)
        """
        parts = re.split(r'(\*\*|\*)', pattern)
        regex_segments: list[str] = []
        for part in parts:
            if part == '**':
                regex_segments.append(r'[^.]+(?:\.[^.]+)*')
            elif part == '*':
                regex_segments.append(r'[^.]+')
            else:
                regex_segments.append(re.escape(part))
        return re.compile('^' + ''.join(regex_segments) + '$')

    def _matches(self, pattern: str, event: str) -> bool:
        """Return True if event matches pattern."""
        if pattern == event:
            return True
        with self._lock:
            compiled = self._pattern_cache.get(pattern)
        if compiled is None:
            compiled = self._compile_pattern(pattern)
        return bool(compiled.fullmatch(event))


# ─── Module-level default bus ────────────────────────────────────────────────

_default_bus = EventBus()

subscribe    = _default_bus.subscribe
unsubscribe  = _default_bus.unsubscribe
publish      = _default_bus.publish
on           = _default_bus.on
subscription = _default_bus.subscription

import pytest
from pubsub import EventBus, PublishResult


# ─── Fixture ────────────────────────────────────────────────────────────────

@pytest.fixture
def bus():
    """A fresh EventBus that uses Option A (collect-and-continue) error strategy."""
    class TestBus(EventBus):
        def _handle_publish_error(self, sub_id, exc, result):
            result.errors.append((sub_id, exc))
    return TestBus()


# ─── Exact subscriptions ─────────────────────────────────────────────────────

def test_exact_subscription_fires(bus):
    received = []
    bus.subscribe("user.created", lambda e, d: received.append(d))
    bus.publish("user.created", {"name": "Alice"})
    assert received == [{"name": "Alice"}]

def test_exact_subscription_does_not_fire_on_other_events(bus):
    received = []
    bus.subscribe("user.created", lambda e, d: received.append(d))
    bus.publish("user.updated", {"name": "Alice"})
    assert received == []


# ─── Unsubscribe ─────────────────────────────────────────────────────────────

def test_unsubscribe_stops_delivery(bus):
    received = []
    sub_id = bus.subscribe("user.created", lambda e, d: received.append(d))
    bus.unsubscribe(sub_id)
    bus.publish("user.created", {})
    assert received == []

def test_unsubscribe_unknown_id_returns_false(bus):
    assert bus.unsubscribe("nonexistent-id") is False

def test_unsubscribe_returns_true_for_valid_id(bus):
    sub_id = bus.subscribe("x", lambda e, d: None)
    assert bus.unsubscribe(sub_id) is True


# ─── Wildcard: single segment (*) ────────────────────────────────────────────

def test_single_wildcard_matches_one_segment(bus):
    hits = []
    bus.subscribe("user.*", lambda e, d: hits.append(e))
    bus.publish("user.created")
    bus.publish("user.deleted")
    assert hits == ["user.created", "user.deleted"]

def test_single_wildcard_does_not_match_two_segments(bus):
    hits = []
    bus.subscribe("user.*", lambda e, d: hits.append(e))
    bus.publish("user.profile.updated")
    assert hits == []

def test_single_wildcard_does_not_match_bare_prefix(bus):
    hits = []
    bus.subscribe("user.*", lambda e, d: hits.append(e))
    bus.publish("user")
    assert hits == []


# ─── Wildcard: multi-segment (**) ────────────────────────────────────────────

def test_double_wildcard_matches_one_segment(bus):
    hits = []
    bus.subscribe("order.**", lambda e, d: hits.append(e))
    bus.publish("order.placed")
    assert "order.placed" in hits

def test_double_wildcard_matches_two_segments(bus):
    hits = []
    bus.subscribe("order.**", lambda e, d: hits.append(e))
    bus.publish("order.item.shipped")
    assert "order.item.shipped" in hits

def test_double_wildcard_matches_three_segments(bus):
    hits = []
    bus.subscribe("order.**", lambda e, d: hits.append(e))
    bus.publish("order.a.b.c")
    assert "order.a.b.c" in hits

def test_double_wildcard_does_not_match_bare_prefix(bus):
    hits = []
    bus.subscribe("order.**", lambda e, d: hits.append(e))
    bus.publish("order")
    assert hits == []

def test_wildcard_in_middle(bus):
    hits = []
    bus.subscribe("*.created", lambda e, d: hits.append(e))
    bus.publish("user.created")
    bus.publish("order.created")
    bus.publish("user.profile.created")   # should NOT match — * is one segment
    assert hits == ["user.created", "order.created"]

def test_double_wildcard_in_middle(bus):
    hits = []
    bus.subscribe("**.created", lambda e, d: hits.append(e))
    bus.publish("user.created")
    bus.publish("user.profile.created")
    assert set(hits) == {"user.created", "user.profile.created"}


# ─── Multiple subscribers ─────────────────────────────────────────────────────

def test_multiple_subscribers_all_fire(bus):
    log = []
    bus.subscribe("x", lambda e, d: log.append("A"))
    bus.subscribe("x", lambda e, d: log.append("B"))
    bus.publish("x")
    assert sorted(log) == ["A", "B"]


# ─── PublishResult ───────────────────────────────────────────────────────────

def test_result_contains_handler_return_values(bus):
    bus.subscribe("ping", lambda e, d: "pong")
    result = bus.publish("ping")
    assert result.results == ["pong"]

def test_result_succeeded_when_no_errors(bus):
    bus.subscribe("ok", lambda e, d: None)
    result = bus.publish("ok")
    assert result.succeeded is True

def test_result_errors_collected_and_other_handlers_run(bus):
    log = []
    bus.subscribe("x", lambda e, d: (_ for _ in ()).throw(ValueError("boom")))
    bus.subscribe("x", lambda e, d: log.append("second"))
    result = bus.publish("x")
    assert not result.succeeded
    assert log == ["second"]   # second handler ran despite first failing


# ─── Decorator syntax ────────────────────────────────────────────────────────

def test_on_decorator(bus):
    hits = []

    @bus.on("app.*")
    def handler(event, data):
        hits.append(event)

    bus.publish("app.start")
    assert hits == ["app.start"]


# ─── Context manager ─────────────────────────────────────────────────────────

def test_subscription_context_manager_unsubscribes(bus):
    hits = []
    with bus.subscription("tmp.*", lambda e, d: hits.append(e)):
        bus.publish("tmp.a")
    bus.publish("tmp.b")           # should not be received
    assert hits == ["tmp.a"]


# ─── Introspection ───────────────────────────────────────────────────────────

def test_subscriber_count_total(bus):
    bus.subscribe("a", lambda e, d: None)
    bus.subscribe("b.*", lambda e, d: None)
    assert bus.subscriber_count() == 2

def test_subscriber_count_for_event(bus):
    bus.subscribe("a", lambda e, d: None)
    bus.subscribe("a.*", lambda e, d: None)
    bus.subscribe("b", lambda e, d: None)
    assert bus.subscriber_count("a.foo") == 1   # only "a.*" matches

def test_clear_removes_all(bus):
    bus.subscribe("a", lambda e, d: None)
    bus.subscribe("b", lambda e, d: None)
    bus.clear()
    assert bus.subscriber_count() == 0

def _handle_publish_error(self, subscription_id, exc, result):
    # Your strategy here