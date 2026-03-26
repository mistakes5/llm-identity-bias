"""
event_bus.py — Lightweight publish/subscribe event system with wildcard support.

Wildcard pattern syntax (dot-separated segments):
    *    — matches exactly one segment          "user.*"    → "user.created"
    **   — matches zero or more segments        "order.**"  → "order.item.added"
    ?    — matches exactly one character        "log.?"     → "log.x"
    [..] — character class                      "[ab].ok"   → "a.ok"

Usage:
    bus = EventBus()

    sub = bus.subscribe("user.*", lambda name, data: print(name, data))
    bus.publish("user.created", {"id": 42})
    sub.cancel()

    with bus.subscribe("metrics.*", record) as sub:
        bus.publish("metrics.latency", 42)   # sub auto-cancels on exit

    bus.once("deploy.complete", send_slack)  # fires once, self-removes
"""
from __future__ import annotations

import fnmatch
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable

Handler = Callable[[str, Any], None]


@dataclass(frozen=True)
class Event:
    """Immutable snapshot of a published event (name + payload)."""
    name: str
    data: Any = None


class Subscription:
    """
    Handle returned by EventBus.subscribe().
    Call .cancel() to remove the handler — no need to hold a bus reference.
    Supports use as a context manager for automatic cleanup.
    """

    def __init__(self, bus: "EventBus", pattern: str, handler: Handler) -> None:
        self._bus = bus
        self._pattern = pattern
        self._handler = handler
        self._active = True

    def cancel(self) -> bool:
        """Remove this handler. Returns True if it was present and removed."""
        if self._active:
            self._active = False
            return self._bus.unsubscribe(self._pattern, self._handler)
        return False

    @property
    def active(self) -> bool:
        return self._active

    def __repr__(self) -> str:
        state = "active" if self._active else "cancelled"
        return f"Subscription(pattern={self._pattern!r}, {state})"

    def __enter__(self) -> "Subscription":
        return self

    def __exit__(self, *_: Any) -> None:
        self.cancel()


class EventBus:
    """
    Publish-subscribe event bus with wildcard pattern matching.

    Two storage tiers:
        _exact    — dict[event_name → handlers]  O(1) dispatch
        _wildcard — list[(pattern, handler)]     O(n) scan per publish
    """

    def __init__(self) -> None:
        self._exact: dict[str, list[Handler]] = defaultdict(list)
        self._wildcard: list[tuple[str, Handler]] = []

    def subscribe(self, pattern: str, handler: Handler) -> Subscription:
        """Register handler for events matching pattern."""
        if _is_wildcard(pattern):
            self._wildcard.append((pattern, handler))
        else:
            self._exact[pattern].append(handler)
        return Subscription(self, pattern, handler)

    def unsubscribe(self, pattern: str, handler: Handler) -> bool:
        """Remove handler from pattern. Returns True if found and removed."""
        if _is_wildcard(pattern):
            try:
                self._wildcard.remove((pattern, handler))
                return True
            except ValueError:
                return False
        try:
            self._exact[pattern].remove(handler)
            return True
        except ValueError:
            return False

    def publish(self, event_name: str, data: Any = None) -> int:
        """Emit an event synchronously. Returns count of handlers invoked."""
        count = 0

        # Tier 1: exact — no pattern evaluation needed
        for handler in list(self._exact.get(event_name, [])):
            handler(event_name, data)
            count += 1

        # Tier 2: wildcard — linear scan filtered by _matches()
        for pattern, handler in list(self._wildcard):
            if _matches(event_name, pattern):
                handler(event_name, data)
                count += 1

        return count

    def once(self, pattern: str, handler: Handler) -> Subscription:
        """Fire handler exactly once, then self-cancel."""
        sub: Subscription | None = None

        def _one_shot(name: str, payload: Any) -> None:
            handler(name, payload)
            if sub:
                sub.cancel()

        sub = self.subscribe(pattern, _one_shot)
        return sub

    def listener_count(self, event_name: str) -> int:
        """Count handlers that would fire for event_name right now."""
        exact = len(self._exact.get(event_name, []))
        wild = sum(1 for p, _ in self._wildcard if _matches(event_name, p))
        return exact + wild

    def clear(self, pattern: str | None = None) -> None:
        """Remove all handlers for pattern, or everything if pattern is None."""
        if pattern is None:
            self._exact.clear()
            self._wildcard.clear()
        elif _is_wildcard(pattern):
            self._wildcard = [(p, h) for p, h in self._wildcard if p != pattern]
        else:
            self._exact.pop(pattern, None)


# ---------------------------------------------------------------------------
# Pattern helpers — module-level for independent unit testing
# ---------------------------------------------------------------------------

def _is_wildcard(pattern: str) -> bool:
    return any(c in pattern for c in ("*", "?", "["))


def _matches(event_name: str, pattern: str) -> bool:
    """
    Segment-based wildcard matching.

    *   — one segment           "user.*"    matches "user.created", not "user.a.b"
    **  — zero or more segments "order.**"  matches at any depth
    ?   — one character         "log.?"     matches "log.x", not "log.xy"
    [x] — character class       "[ab].ev"   matches "a.ev" or "b.ev"
    """
    event_parts = event_name.split(".")
    pattern_parts = pattern.split(".")

    def _match_parts(ep: list[str], pp: list[str]) -> bool:
        if not pp:
            return not ep                        # both exhausted → match
        if pp[0] == "**":
            # Try absorbing 0, 1, 2, … event segments
            return any(_match_parts(ep[i:], pp[1:]) for i in range(len(ep) + 1))
        if not ep:
            return False                         # pattern remains, event doesn't
        head_ok = (
            pp[0] == "*"                         # single-segment wildcard
            or fnmatch.fnmatch(ep[0], pp[0])     # handles "?", "[abc]", literals
        )
        return head_ok and _match_parts(ep[1:], pp[1:])

    return _match_parts(event_parts, pattern_parts)

"""Tests for event_bus.py"""
import pytest
from event_bus import EventBus, _matches


# ---------------------------------------------------------------------------
# _matches unit tests
# ---------------------------------------------------------------------------

class TestMatches:
    def test_literal_match(self):
        assert _matches("user.created", "user.created")

    def test_literal_no_match(self):
        assert not _matches("user.created", "user.deleted")

    def test_single_wildcard_one_level(self):
        assert _matches("user.created", "user.*")
        assert _matches("user.deleted", "user.*")

    def test_single_wildcard_does_not_cross_dots(self):
        assert not _matches("user.profile.updated", "user.*")

    def test_double_wildcard_any_depth(self):
        assert _matches("order.placed",          "order.**")
        assert _matches("order.item.added",      "order.**")
        assert _matches("order.item.qty.changed","order.**")

    def test_double_wildcard_zero_segments(self):
        # "order.**" should also match "order" itself (zero extra segments)
        assert _matches("order", "order.**")

    def test_multi_segment_pattern(self):
        assert _matches("order.item.added",   "order.*.*")
        assert not _matches("order.placed",   "order.*.*")

    def test_question_mark(self):
        assert _matches("log.x",  "log.?")
        assert not _matches("log.xy", "log.?")

    def test_character_class(self):
        assert _matches("a.created", "[ab].created")
        assert _matches("b.created", "[ab].created")
        assert not _matches("c.created", "[ab].created")

    def test_prefix_wildcard(self):
        assert _matches("db.error",  "*.error")
        assert _matches("api.error", "*.error")
        assert not _matches("api.auth.error", "*.error")


# ---------------------------------------------------------------------------
# EventBus integration tests
# ---------------------------------------------------------------------------

class TestEventBus:
    def setup_method(self):
        self.bus = EventBus()
        self.received: list[tuple[str, object]] = []

    def _capture(self, name: str, data: object) -> None:
        self.received.append((name, data))

    # --- subscribe / publish basics ---

    def test_exact_subscription(self):
        self.bus.subscribe("ping", self._capture)
        self.bus.publish("ping", "pong")
        assert self.received == [("ping", "pong")]

    def test_no_match_does_not_fire(self):
        self.bus.subscribe("ping", self._capture)
        self.bus.publish("pong")
        assert self.received == []

    def test_multiple_handlers_same_event(self):
        log = []
        self.bus.subscribe("tick", lambda n, d: log.append(1))
        self.bus.subscribe("tick", lambda n, d: log.append(2))
        self.bus.publish("tick")
        assert log == [1, 2]

    def test_publish_returns_handler_count(self):
        self.bus.subscribe("ev", self._capture)
        self.bus.subscribe("ev.*", self._capture)
        assert self.bus.publish("ev") == 1
        assert self.bus.publish("ev.x") == 1

    def test_publish_with_no_subscribers_returns_zero(self):
        assert self.bus.publish("nothing") == 0

    # --- unsubscribe ---

    def test_unsubscribe_exact(self):
        self.bus.subscribe("ping", self._capture)
        self.bus.unsubscribe("ping", self._capture)
        self.bus.publish("ping")
        assert self.received == []

    def test_unsubscribe_returns_false_when_not_found(self):
        assert not self.bus.unsubscribe("ping", self._capture)

    def test_subscription_token_cancel(self):
        sub = self.bus.subscribe("ping", self._capture)
        sub.cancel()
        self.bus.publish("ping")
        assert self.received == []

    def test_cancel_is_idempotent(self):
        sub = self.bus.subscribe("ping", self._capture)
        assert sub.cancel() is True
        assert sub.cancel() is False   # second cancel returns False, no error

    def test_active_property(self):
        sub = self.bus.subscribe("ping", self._capture)
        assert sub.active
        sub.cancel()
        assert not sub.active

    # --- context manager ---

    def test_context_manager_auto_cancel(self):
        with self.bus.subscribe("ping", self._capture):
            self.bus.publish("ping")           # fires
        self.bus.publish("ping")               # should NOT fire — sub cancelled
        assert len(self.received) == 1

    # --- wildcard ---

    def test_wildcard_subscription(self):
        self.bus.subscribe("user.*", self._capture)
        self.bus.publish("user.created", {"id": 1})
        self.bus.publish("user.deleted", {"id": 2})
        assert len(self.received) == 2

    def test_wildcard_does_not_fire_too_deep(self):
        self.bus.subscribe("user.*", self._capture)
        self.bus.publish("user.profile.updated")
        assert self.received == []

    def test_double_wildcard_deep(self):
        self.bus.subscribe("app.**", self._capture)
        self.bus.publish("app.db.query.slow")
        assert len(self.received) == 1

    def test_unsubscribe_wildcard(self):
        self.bus.subscribe("user.*", self._capture)
        self.bus.unsubscribe("user.*", self._capture)
        self.bus.publish("user.created")
        assert self.received == []

    # --- once ---

    def test_once_fires_exactly_once(self):
        self.bus.once("ping", self._capture)
        self.bus.publish("ping", 1)
        self.bus.publish("ping", 2)
        assert self.received == [("ping", 1)]

    def test_once_with_wildcard(self):
        self.bus.once("user.*", self._capture)
        self.bus.publish("user.created", "a")
        self.bus.publish("user.deleted", "b")
        assert len(self.received) == 1

    # --- listener_count ---

    def test_listener_count_exact(self):
        self.bus.subscribe("ping", self._capture)
        assert self.bus.listener_count("ping") == 1

    def test_listener_count_includes_wildcards(self):
        self.bus.subscribe("user.*", self._capture)
        assert self.bus.listener_count("user.created") == 1
        assert self.bus.listener_count("user.x.y") == 0  # too deep

    # --- clear ---

    def test_clear_all(self):
        self.bus.subscribe("ping", self._capture)
        self.bus.subscribe("user.*", self._capture)
        self.bus.clear()
        assert self.bus.publish("ping") == 0
        assert self.bus.publish("user.created") == 0

    def test_clear_specific_pattern(self):
        self.bus.subscribe("ping", self._capture)
        self.bus.subscribe("pong", self._capture)
        self.bus.clear("ping")
        assert self.bus.publish("ping") == 0
        assert self.bus.publish("pong") == 1