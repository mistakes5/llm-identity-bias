"""
Publish-subscribe event bus with wildcard pattern matching.

Pattern syntax:
    user.created        — exact match
    user.*              — * matches exactly ONE dot-separated segment
    user.**             — ** matches ZERO OR MORE segments (recursive)
    **.created          — works at any position
    **                  — matches every event

Examples:
    "order.*"    matches "order.placed"          ✓
                 matches "order.shipped"         ✓
                 matches "order.details.updated" ✗  (two segments, not one)

    "order.**"   matches "order.placed"          ✓
                 matches "order.details.updated" ✓
                 matches "order"                 ✓  (zero trailing segments)

    "**.failed"  matches "job.run.failed"        ✓
                 matches "payment.failed"        ✓
                 matches "failed"                ✓
"""

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable


# ── Data structures ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Subscription:
    """Immutable record of a single registration. Returned as an opaque handle."""
    id: str
    pattern: str
    callback: Callable[[str, Any], None]


@dataclass
class PublishResult:
    """Aggregated outcome of a single publish call."""
    event: str
    notified: int = 0
    errors: list[tuple[str, Exception]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """True iff every matched subscriber was invoked without raising."""
        return not self.errors

    def __repr__(self) -> str:
        status = "ok" if self.ok else f"{len(self.errors)} error(s)"
        return f"PublishResult(event={self.event!r}, notified={self.notified}, status={status})"


# ── Pattern matching ──────────────────────────────────────────────────────────

def _match_parts(pattern_parts: list[str], event_parts: list[str]) -> bool:
    """
    Recursive wildcard matcher for dot-separated event paths.

    ┌─────────────────────────────────────────────────────────────────────┐
    │  YOUR IMPLEMENTATION GOES HERE                                      │
    │                                                                     │
    │  Handle these four cases in order:                                  │
    │                                                                     │
    │  1. Both lists empty               → full match, return True        │
    │  2. pattern empty, event not       → leftover event with no         │
    │                                      pattern left → return False    │
    │  3. Head of pattern is "**"        → try matching the REST of the   │
    │                                      pattern against every suffix   │
    │                                      of event_parts (0 to N)        │
    │  4. Head is "*" OR matches exactly → consume one segment from each, │
    │                                      recurse on tails               │
    │     Otherwise                      → return False                   │
    │                                                                     │
    │  Rules:                                                             │
    │  - Do NOT use `re` or `fnmatch`                                     │
    │  - Must handle "**" at any position (prefix, middle, suffix, alone) │
    │  - `head, *tail = lst` cleanly splits a list in Python              │
    └─────────────────────────────────────────────────────────────────────┘
    """
    raise NotImplementedError(
        "Implement _match_parts — see the docstring for the four cases."
    )


def pattern_matches(pattern: str, event: str) -> bool:
    """Public entry point. Returns True if *event* matches *pattern*."""
    return _match_parts(pattern.split("."), event.split("."))


# ── EventBus ──────────────────────────────────────────────────────────────────

class EventBus:
    """
    Thread-safe publish-subscribe event bus.

    Typical usage::

        bus = EventBus()

        token = bus.subscribe("order.*", on_order_event)
        result = bus.publish("order.placed", {"id": 42, "total": 99.95})
        bus.unsubscribe(token)

    All methods are thread-safe. Callbacks are invoked synchronously on
    the publishing thread. Errors in one callback never silently block others.
    """

    def __init__(self) -> None:
        # RLock (reentrant) lets a callback call publish() without deadlocking.
        self._subs: dict[str, Subscription] = {}
        self._lock = threading.RLock()

    # ── Core API ──────────────────────────────────────────────────────────────

    def subscribe(self, pattern: str, callback: Callable[[str, Any], None]) -> str:
        """
        Register *callback* for all events matching *pattern*.

        Returns a subscription ID — pass to :meth:`unsubscribe` when done.

        Raises:
            TypeError: If *callback* is not callable.
        """
        if not callable(callback):
            raise TypeError(
                f"callback must be callable, got {type(callback).__name__!r}"
            )
        sub_id = str(uuid.uuid4())
        with self._lock:
            self._subs[sub_id] = Subscription(
                id=sub_id, pattern=pattern, callback=callback
            )
        return sub_id

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Remove the subscription identified by *subscription_id*.

        Returns True if found and removed; False if not found.
        """
        with self._lock:
            return self._subs.pop(subscription_id, None) is not None

    def publish(self, event: str, data: Any = None) -> PublishResult:
        """
        Deliver *event* (with optional *data*) to every matching subscriber.

        Collect-all error strategy: if a callback raises, the exception is
        captured into PublishResult.errors and delivery continues. A snapshot
        of subscriptions is taken before iteration so concurrent
        subscribe/unsubscribe calls are safe.

        Returns:
            PublishResult with a `notified` count and any `errors`.
        """
        with self._lock:
            snapshot = list(self._subs.values())

        result = PublishResult(event=event)

        for sub in snapshot:
            if pattern_matches(sub.pattern, event):
                try:
                    sub.callback(event, data)
                    result.notified += 1
                except Exception as exc:          # noqa: BLE001
                    result.errors.append((sub.id, exc))

        return result

    # ── Introspection ─────────────────────────────────────────────────────────

    def listeners(self, event: str) -> list[str]:
        """Return IDs of subscriptions whose pattern matches *event*."""
        with self._lock:
            return [
                sid for sid, sub in self._subs.items()
                if pattern_matches(sub.pattern, event)
            ]

    def clear(self) -> int:
        """Remove all subscriptions. Returns count removed."""
        with self._lock:
            count = len(self._subs)
            self._subs.clear()
        return count

    def __len__(self) -> int:
        with self._lock:
            return len(self._subs)

    def __repr__(self) -> str:
        return f"EventBus(subscriptions={len(self)})"

"""
Tests for EventBus — run with: python -m pytest test_event_bus.py -v
These act as a specification for _match_parts, so they drive your implementation.
"""

import pytest
from event_bus import EventBus, pattern_matches


# ── Pattern matching spec ─────────────────────────────────────────────────────

class TestPatternMatching:

    def test_exact_match(self):
        assert pattern_matches("user.created", "user.created")

    def test_exact_no_match(self):
        assert not pattern_matches("user.created", "user.deleted")

    def test_single_wildcard_one_segment(self):
        assert pattern_matches("user.*", "user.created")
        assert pattern_matches("user.*", "user.deleted")

    def test_single_wildcard_does_not_span_segments(self):
        assert not pattern_matches("user.*", "user.profile.updated")

    def test_double_wildcard_matches_zero_segments(self):
        assert pattern_matches("user.**", "user")   # trailing ** = optional

    def test_double_wildcard_matches_one_segment(self):
        assert pattern_matches("user.**", "user.created")

    def test_double_wildcard_matches_deep_path(self):
        assert pattern_matches("user.**", "user.profile.picture.updated")

    def test_catch_all(self):
        assert pattern_matches("**", "absolutely.anything.at.all")
        assert pattern_matches("**", "simple")

    def test_wildcard_in_middle(self):
        assert pattern_matches("a.*.c", "a.b.c")
        assert not pattern_matches("a.*.c", "a.b.d")
        assert not pattern_matches("a.*.c", "a.b.x.c")  # * is not **

    def test_double_wildcard_in_middle(self):
        assert pattern_matches("a.**.z", "a.b.c.d.z")
        assert pattern_matches("a.**.z", "a.z")          # zero middle segments

    def test_prefix_double_wildcard(self):
        assert pattern_matches("**.created", "user.created")
        assert pattern_matches("**.created", "org.user.created")
        assert pattern_matches("**.created", "created")

    def test_no_partial_segment_match(self):
        # "use" must not match the segment "user"
        assert not pattern_matches("use.*", "user.created")


# ── EventBus behaviour ────────────────────────────────────────────────────────

class TestEventBus:

    def test_subscribe_and_publish(self):
        bus = EventBus()
        received = []
        bus.subscribe("click", lambda e, d: received.append(d))
        bus.publish("click", {"x": 10})
        assert received == [{"x": 10}]

    def test_callback_receives_event_name(self):
        bus = EventBus()
        names = []
        bus.subscribe("order.*", lambda e, d: names.append(e))
        bus.publish("order.placed")
        bus.publish("order.shipped")
        assert names == ["order.placed", "order.shipped"]

    def test_unsubscribe_stops_delivery(self):
        bus = EventBus()
        received = []
        token = bus.subscribe("click", lambda e, d: received.append(d))
        bus.unsubscribe(token)
        bus.publish("click", {"x": 10})
        assert received == []

    def test_unsubscribe_unknown_id_returns_false(self):
        bus = EventBus()
        assert bus.unsubscribe("nonexistent-id") is False

    def test_multiple_subscribers_all_notified(self):
        bus = EventBus()
        a, b = [], []
        bus.subscribe("evt", lambda e, d: a.append(d))
        bus.subscribe("evt", lambda e, d: b.append(d))
        bus.publish("evt", 42)
        assert a == [42] and b == [42]

    def test_wildcard_subscription(self):
        bus = EventBus()
        events = []
        bus.subscribe("order.*", lambda e, d: events.append(e))
        bus.publish("order.placed")
        bus.publish("order.shipped")
        bus.publish("order.details.updated")  # should NOT match
        assert events == ["order.placed", "order.shipped"]

    def test_publish_result_notified_count(self):
        bus = EventBus()
        bus.subscribe("x", lambda e, d: None)
        bus.subscribe("x", lambda e, d: None)
        result = bus.publish("x")
        assert result.notified == 2
        assert result.ok

    def test_publish_result_collects_errors(self):
        bus = EventBus()

        def boom(e, d):
            raise RuntimeError("callback failure")

        bus.subscribe("x", boom)
        result = bus.publish("x")
        assert not result.ok
        assert len(result.errors) == 1
        assert isinstance(result.errors[0][1], RuntimeError)

    def test_failing_callback_does_not_block_peers(self):
        """Collect-all: error in subscriber A must not silence subscriber B."""
        bus = EventBus()
        reached = []

        def bad(e, d):
            raise RuntimeError("bad")

        bus.subscribe("x", bad)
        bus.subscribe("x", lambda e, d: reached.append(True))

        result = bus.publish("x")
        assert reached == [True]          # second subscriber still ran
        assert len(result.errors) == 1

    def test_no_match_returns_zero_notified(self):
        bus = EventBus()
        bus.subscribe("other.*", lambda e, d: None)
        result = bus.publish("unrelated.event")
        assert result.notified == 0

    def test_len_tracks_subscriptions(self):
        bus = EventBus()
        assert len(bus) == 0
        t1 = bus.subscribe("a", lambda e, d: None)
        t2 = bus.subscribe("b", lambda e, d: None)
        assert len(bus) == 2
        bus.unsubscribe(t1)
        assert len(bus) == 1
        bus.unsubscribe(t2)
        assert len(bus) == 0

    def test_clear(self):
        bus = EventBus()
        bus.subscribe("a", lambda e, d: None)
        bus.subscribe("b", lambda e, d: None)
        count = bus.clear()
        assert count == 2
        assert len(bus) == 0

    def test_listeners_introspection(self):
        bus = EventBus()
        t = bus.subscribe("user.*", lambda e, d: None)
        bus.subscribe("order.*", lambda e, d: None)
        ids = bus.listeners("user.created")
        assert ids == [t]

    def test_reentrant_publish(self):
        """A callback may safely call publish() without deadlocking (RLock)."""
        bus = EventBus()
        secondary = []
        bus.subscribe("primary", lambda e, d: bus.publish("secondary", d))
        bus.subscribe("secondary", lambda e, d: secondary.append(d))
        bus.publish("primary", "ping")
        assert secondary == ["ping"]

    def test_thread_safety(self):
        """Concurrent publishes from multiple threads must not corrupt state."""
        bus = EventBus()
        results = []
        lock = threading.Lock()

        def handler(e, d):
            with lock:
                results.append(d)

        bus.subscribe("**", handler)

        threads = [
            threading.Thread(target=lambda i=i: bus.publish("evt", i))
            for i in range(50)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sorted(results) == list(range(50))

def _match_parts(pattern_parts: list[str], event_parts: list[str]) -> bool:
    # case 1 — base case: total match
    if not pattern_parts and not event_parts:
        return ...

    # case 2 — pattern exhausted but event still has segments
    if not pattern_parts:
        return ...

    head, *rest_p = pattern_parts

    # case 3 — greedy double wildcard: try consuming 0, 1, 2, … event segments
    if head == "**":
        for i in range(len(event_parts) + 1):
            if _match_parts(rest_p, event_parts[i:]):
                return True
        return False

    # case 4 — single wildcard OR exact literal
    ...