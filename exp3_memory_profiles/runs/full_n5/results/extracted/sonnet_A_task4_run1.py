"""
event_bus.py — Thread-safe publish-subscribe event bus with wildcard patterns.

Pattern Syntax
--------------
  *    matches any single segment (chars between dots, no dots allowed)
  **   matches any number of segments, including dots
  ?    matches any single non-dot character
  .    literal dot separator

Examples
--------
  "user.created"          exact match
  "user.*"                user.created, user.deleted — NOT user.profile.updated
  "order.**.shipped"      order.shipped, order.express.shipped, ...
  "**"                    every event ever published
  "?.login"               a.login, x.login — NOT ab.login
"""
from __future__ import annotations

import re
import threading
import uuid
from dataclasses import dataclass
from typing import Any, Callable


# ─── Public Types ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SubscriptionHandle:
    """Opaque receipt returned by subscribe(). Pass to unsubscribe()."""
    id: str
    pattern: str

    def __repr__(self) -> str:
        return f"<Subscription pattern={self.pattern!r} id={self.id[:8]}…>"


# ─── Internal ─────────────────────────────────────────────────────────────────


@dataclass
class _Subscription:
    handle: SubscriptionHandle
    handler: Callable[[str, Any], None]
    regex: re.Pattern[str]
    once: bool = False


# ─── Event Bus ────────────────────────────────────────────────────────────────


class EventBus:
    """
    Thread-safe publish-subscribe event bus.

    Design notes
    ------------
    • Subscribers are *snapshotted* under the lock then called *outside* it —
      so handlers can freely call subscribe()/unsubscribe() without deadlocking.
    • `once` subscriptions are removed BEFORE invocation to prevent double-fire
      under concurrent publishes on different threads.
    • All handler exceptions are collected; every handler runs, then the first
      exception is re-raised — a bad handler never silences its siblings.
    """

    def __init__(self) -> None:
        self._subs: dict[str, _Subscription] = {}
        self._lock = threading.RLock()   # RLock: handlers can re-enter safely

    # ── Core API ──────────────────────────────────────────────────────────────

    def subscribe(
        self,
        pattern: str,
        handler: Callable[[str, Any], None],
        *,
        once: bool = False,
    ) -> SubscriptionHandle:
        """
        Register *handler* for every event matching *pattern*.

        handler signature:  handler(event_name: str, data: Any) -> None

        Returns a SubscriptionHandle — keep it to call unsubscribe() later.
        Set once=True to auto-remove after the first firing.
        """
        regex = _compile_pattern(pattern)
        handle = SubscriptionHandle(id=str(uuid.uuid4()), pattern=pattern)
        sub = _Subscription(handle=handle, handler=handler, regex=regex, once=once)
        with self._lock:
            self._subs[handle.id] = sub
        return handle

    def once(self, pattern: str, handler: Callable[[str, Any], None]) -> SubscriptionHandle:
        """Convenience alias: subscribe(..., once=True)."""
        return self.subscribe(pattern, handler, once=True)

    def unsubscribe(self, handle: SubscriptionHandle) -> bool:
        """Remove a subscription. Returns True if found, False if already gone."""
        with self._lock:
            return self._subs.pop(handle.id, None) is not None

    def publish(self, event: str, data: Any = None) -> int:
        """
        Dispatch *event* to all matching subscribers (synchronous).

        Returns the number of handlers invoked.
        Raises RuntimeError (wrapping the first failure) if any handler raises.
        All handlers still run even when some fail.
        """
        with self._lock:
            matching = [s for s in self._subs.values() if s.regex.fullmatch(event)]
            # Remove once-subs under lock BEFORE invoking, to prevent double-fire
            for sub in matching:
                if sub.once:
                    self._subs.pop(sub.handle.id, None)

        errors: list[tuple[_Subscription, BaseException]] = []
        for sub in matching:
            try:
                sub.handler(event, data)
            except Exception as exc:
                errors.append((sub, exc))

        if errors:
            first_sub, first_exc = errors[0]
            raise RuntimeError(
                f"{len(errors)} handler(s) raised. "
                f"First failure in pattern={first_sub.handle.pattern!r}"
            ) from first_exc

        return len(matching)

    # ── Introspection ─────────────────────────────────────────────────────────

    def subscribers_for(self, event: str) -> int:
        """Count subscriptions that would receive *event*."""
        with self._lock:
            return sum(1 for s in self._subs.values() if s.regex.fullmatch(event))

    def clear(self) -> None:
        """Remove all subscriptions."""
        with self._lock:
            self._subs.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._subs)

    def __repr__(self) -> str:
        return f"EventBus(subscriptions={len(self)})"


# ─── Pattern Compilation ──────────────────────────────────────────────────────


def _compile_pattern(pattern: str) -> re.Pattern[str]:
    """
    Translate a glob-style event pattern into a compiled regex.

    Transformation rules
    --------------------
      **   ->  .*         spans dots and segments
      *    ->  [^.]+      one-or-more non-dot chars (single segment only)
      ?    ->  [^.]       exactly one non-dot char
      .    ->  \\.         literal dot
      other -> re.escape  all other metacharacters neutralised

    Strategy
    --------
    1. Split on "**" to separate regions that can/can't cross segment boundaries.
    2. Within each fragment: re.escape() to neutralise metacharacters, then
       replace the escaped \\* with [^.]+ and \\? with [^.].
    3. Rejoin fragments with .* (the ** equivalent).

    TODO — implement the body below
    ─────────────────────────────────────────────────────────────────────────
    Hints:
      • pattern.split("**") gives you fragments between each **.
      • After re.escape(fragment), the original * is now \\* (two chars)
        and ? is now \\? — both safe to str.replace back to regex tokens.
      • Join processed fragments with ".*" and compile with re.DOTALL.
      • Edge case: pattern == "**" → split gives ['', ''] → join gives ".*" ✓

    Trade-offs:
      • [^.]+  requires at least one char per segment.  [^.]* allows empty
        segments.  Which matches your domain semantics?
      • Greedy .*  vs lazy .*?  — greedy is usually right unless you have
        ** on both sides of a literal and need the shortest match.
    ─────────────────────────────────────────────────────────────────────────
    """
    # ── Your implementation goes here ─────────────────────────────────────────
    raise NotImplementedError("_compile_pattern not yet implemented — see the docstring")

"""Tests for EventBus — all pass once _compile_pattern is implemented."""
import pytest
from event_bus import EventBus, SubscriptionHandle


# ── Exact match ───────────────────────────────────────────────────────────────

def test_exact_match_fires():
    bus = EventBus()
    received = []
    bus.subscribe("user.created", lambda e, d: received.append((e, d)))
    bus.publish("user.created", {"id": 1})
    assert received == [("user.created", {"id": 1})]

def test_exact_match_no_cross_fire():
    bus = EventBus()
    received = []
    bus.subscribe("user.created", lambda e, d: received.append(e))
    bus.publish("user.deleted", None)
    assert received == []


# ── Single-segment wildcard (*) ───────────────────────────────────────────────

def test_star_matches_single_segment():
    bus = EventBus()
    hits = []
    bus.subscribe("user.*", lambda e, d: hits.append(e))
    bus.publish("user.created", None)
    bus.publish("user.deleted", None)
    assert hits == ["user.created", "user.deleted"]

def test_star_does_not_cross_dots():
    bus = EventBus()
    hits = []
    bus.subscribe("user.*", lambda e, d: hits.append(e))
    bus.publish("user.profile.updated", None)   # two levels deep — should NOT match
    assert hits == []

def test_star_requires_non_empty_segment():
    bus = EventBus()
    hits = []
    bus.subscribe("user.*", lambda e, d: hits.append(e))
    bus.publish("user.", None)   # empty segment — behaviour depends on [^.]+ vs [^.]*
    # With [^.]+ this should not match; document the expected behaviour:
    assert hits == []            # adjust if you chose [^.]*


# ── Multi-segment wildcard (**) ───────────────────────────────────────────────

def test_double_star_matches_everything():
    bus = EventBus()
    hits = []
    bus.subscribe("**", lambda e, d: hits.append(e))
    bus.publish("a", None)
    bus.publish("a.b", None)
    bus.publish("a.b.c.d", None)
    assert hits == ["a", "a.b", "a.b.c.d"]

def test_double_star_in_middle():
    bus = EventBus()
    hits = []
    bus.subscribe("order.**.shipped", lambda e, d: hits.append(e))
    bus.publish("order.shipped", None)
    bus.publish("order.express.shipped", None)
    bus.publish("order.uk.next.day.shipped", None)
    bus.publish("order.express.delivered", None)   # wrong suffix
    assert hits == ["order.shipped", "order.express.shipped", "order.uk.next.day.shipped"]


# ── Single-char wildcard (?) ──────────────────────────────────────────────────

def test_question_mark_matches_one_char():
    bus = EventBus()
    hits = []
    bus.subscribe("?.login", lambda e, d: hits.append(e))
    bus.publish("a.login", None)
    bus.publish("x.login", None)
    bus.publish("ab.login", None)    # two chars — must NOT match
    assert hits == ["a.login", "x.login"]


# ── Subscribe / Unsubscribe ───────────────────────────────────────────────────

def test_unsubscribe_stops_delivery():
    bus = EventBus()
    hits = []
    handle = bus.subscribe("x", lambda e, d: hits.append(e))
    bus.publish("x", None)
    bus.unsubscribe(handle)
    bus.publish("x", None)
    assert hits == ["x"]   # only the first publish

def test_unsubscribe_returns_false_when_already_gone():
    bus = EventBus()
    handle = bus.subscribe("x", lambda e, d: None)
    bus.unsubscribe(handle)
    assert bus.unsubscribe(handle) is False

def test_unsubscribe_inside_handler():
    """A handler can safely unsubscribe itself without deadlock."""
    bus = EventBus()
    hits = []
    handle = None

    def self_removing(event, data):
        hits.append(event)
        bus.unsubscribe(handle)

    handle = bus.subscribe("ping", self_removing)
    bus.publish("ping", None)
    bus.publish("ping", None)   # handle removed; should not fire again
    assert hits == ["ping"]


# ── once() ────────────────────────────────────────────────────────────────────

def test_once_fires_exactly_once():
    bus = EventBus()
    hits = []
    bus.once("boot", lambda e, d: hits.append(e))
    bus.publish("boot", None)
    bus.publish("boot", None)
    assert hits == ["boot"]

def test_once_subscription_removed_after_fire():
    bus = EventBus()
    bus.once("boot", lambda e, d: None)
    assert len(bus) == 1
    bus.publish("boot", None)
    assert len(bus) == 0


# ── Multiple subscribers ──────────────────────────────────────────────────────

def test_multiple_handlers_all_called():
    bus = EventBus()
    log = []
    bus.subscribe("evt", lambda e, d: log.append("A"))
    bus.subscribe("evt", lambda e, d: log.append("B"))
    bus.subscribe("evt", lambda e, d: log.append("C"))
    bus.publish("evt", None)
    assert sorted(log) == ["A", "B", "C"]

def test_publish_returns_handler_count():
    bus = EventBus()
    bus.subscribe("x", lambda e, d: None)
    bus.subscribe("x", lambda e, d: None)
    bus.subscribe("y", lambda e, d: None)
    assert bus.publish("x") == 2
    assert bus.publish("y") == 1
    assert bus.publish("z") == 0


# ── Error handling ────────────────────────────────────────────────────────────

def test_failing_handler_does_not_silence_others():
    bus = EventBus()
    log = []
    bus.subscribe("e", lambda e, d: (_ for _ in ()).throw(ValueError("boom")))
    bus.subscribe("e", lambda e, d: log.append("ok"))
    with pytest.raises(RuntimeError):
        bus.publish("e", None)
    assert log == ["ok"]   # second handler still ran


# ── Thread safety ─────────────────────────────────────────────────────────────

def test_concurrent_publishes_do_not_race():
    bus = EventBus()
    counter = [0]
    lock = threading.Lock()

    def inc(e, d):
        with lock:
            counter[0] += 1

    for _ in range(10):
        bus.subscribe("tick", inc)

    threads = [threading.Thread(target=bus.publish, args=("tick",)) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert counter[0] == 50 * 10   # 50 publishes × 10 handlers each


# ── Utility ───────────────────────────────────────────────────────────────────

def test_clear_removes_all():
    bus = EventBus()
    bus.subscribe("a", lambda e, d: None)
    bus.subscribe("b", lambda e, d: None)
    bus.clear()
    assert len(bus) == 0

def test_subscribers_for():
    bus = EventBus()
    bus.subscribe("user.*", lambda e, d: None)
    bus.subscribe("user.*", lambda e, d: None)
    bus.subscribe("order.*", lambda e, d: None)
    assert bus.subscribers_for("user.created") == 2
    assert bus.subscribers_for("order.placed") == 1
    assert bus.subscribers_for("payment.done") == 0