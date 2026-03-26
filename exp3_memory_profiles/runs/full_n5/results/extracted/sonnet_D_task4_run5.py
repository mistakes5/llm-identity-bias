"""
Publish-subscribe event bus with wildcard support.

Wildcard patterns (dot-separated segments):
  *   – matches exactly one segment  (user.* → user.created, NOT user.profile.updated)
  **  – matches one or more segments (user.** → user.created AND user.profile.updated)
  ?   – matches any single character within a segment

Thread-safe; handlers may subscribe/unsubscribe during publish.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from fnmatch import fnmatchcase
from typing import Any

log = logging.getLogger(__name__)


# ── Public types ──────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Event:
    """Immutable envelope delivered to every matched handler."""
    topic: str
    data: Any = None


@dataclass
class Subscription:
    """Opaque handle returned by subscribe(). Pass back to unsubscribe()."""
    pattern: str
    handler: Callable[[Event], None]
    _id: int = field(default_factory=lambda: next(_id_counter))

    def __hash__(self)  -> int:      return self._id
    def __eq__(self, o) -> bool:     return isinstance(o, Subscription) and self._id == o._id


_id_counter = iter(range(10 ** 12))


# ── Error policy ──────────────────────────────────────────────────────────────

class HandlerError(Exception):
    """Raised by RAISE mode after all handlers have been attempted."""


class ErrorPolicy:
    LOG   = "log"    # log exception, continue to next subscriber  (default)
    RAISE = "raise"  # collect all errors, raise HandlerError after publish
    SKIP  = "skip"   # silently swallow


# ── Core bus ──────────────────────────────────────────────────────────────────

class EventBus:
    """
    Thread-safe publish-subscribe event bus.

        bus = EventBus()
        sub = bus.subscribe("user.*", lambda e: print(e.data))
        bus.publish("user.created", {"id": 42})
        bus.unsubscribe(sub)
    """

    def __init__(self, error_policy: str = ErrorPolicy.LOG) -> None:
        if error_policy not in (ErrorPolicy.LOG, ErrorPolicy.RAISE, ErrorPolicy.SKIP):
            raise ValueError(f"Unknown error_policy: {error_policy!r}")
        self._policy = error_policy
        self._lock   = threading.RLock()   # reentrant: handlers may subscribe during publish
        self._subs: list[Subscription] = []

    # ── subscribe ─────────────────────────────────────────────────────────────

    def subscribe(self, pattern: str, handler: Callable[[Event], None]) -> Subscription:
        """
        Register *handler* for every topic matching *pattern*.
        Returns a Subscription token — keep it to unsubscribe later.
        """
        if not callable(handler):
            raise TypeError("handler must be callable")
        sub = Subscription(pattern=pattern, handler=handler)
        with self._lock:
            self._subs.append(sub)
        log.debug("subscribed %r → %r (id=%d)", pattern, handler, sub._id)
        return sub

    # ── unsubscribe ───────────────────────────────────────────────────────────

    def unsubscribe(self, subscription: Subscription) -> bool:
        """Cancel a subscription. Returns True if found. Idempotent."""
        with self._lock:
            try:
                self._subs.remove(subscription)
                log.debug("unsubscribed id=%d", subscription._id)
                return True
            except ValueError:
                return False

    # ── publish ───────────────────────────────────────────────────────────────

    def publish(self, topic: str, data: Any = None) -> int:
        """
        Emit an event. Returns the count of handlers invoked.
        Snapshot before iterating so mid-publish mutations are safe.
        """
        event  = Event(topic=topic, data=data)
        errors: list[tuple[Subscription, Exception]] = []

        with self._lock:
            candidates = list(self._subs)          # snapshot

        matched = [s for s in candidates if _matches(s.pattern, topic)]

        for sub in matched:
            try:
                sub.handler(event)
            except Exception as exc:
                if   self._policy == ErrorPolicy.RAISE: errors.append((sub, exc))
                elif self._policy == ErrorPolicy.LOG:
                    log.exception("handler %r raised on %r", sub.handler, topic)
                # SKIP: pass

        if errors:
            sub0, exc0 = errors[0]
            raise HandlerError(
                f"{len(errors)} handler(s) failed on {topic!r}; "
                f"first from pattern {sub0.pattern!r}"
            ) from exc0

        log.debug("published %r → %d handlers", topic, len(matched))
        return len(matched)

    # ── helpers ───────────────────────────────────────────────────────────────

    def subscriber_count(self, pattern: str | None = None) -> int:
        with self._lock:
            if pattern is None:
                return len(self._subs)
            return sum(1 for s in self._subs if s.pattern == pattern)

    def clear(self) -> None:
        """Remove all subscriptions (test teardown)."""
        with self._lock:
            self._subs.clear()


# ── Pattern matching ──────────────────────────────────────────────────────────

def _matches(pattern: str, topic: str) -> bool:
    if "**" in pattern:
        return _deep_match(pattern.split("."), topic.split("."))

    p_parts = pattern.split(".")
    t_parts = topic.split(".")
    if len(p_parts) != len(t_parts):
        return False
    return all(fnmatchcase(t, p) for p, t in zip(p_parts, t_parts))


def _deep_match(p_parts: list[str], t_parts: list[str]) -> bool:
    """Handles ** by consuming 1..N topic segments recursively."""
    if not p_parts and not t_parts:
        return True
    if not p_parts:
        return False

    head, *tail_p = p_parts

    if head == "**":
        for i in range(1, len(t_parts) + 1):
            if _deep_match(tail_p, t_parts[i:]):
                return True
        return False

    if not t_parts:
        return False

    return fnmatchcase(t_parts[0], head) and _deep_match(tail_p, t_parts[1:])

import pytest
from event_bus import EventBus, ErrorPolicy, HandlerError


@pytest.fixture
def bus():
    b = EventBus()
    yield b
    b.clear()


# ── Basic pub/sub ─────────────────────────────────────────────────────────────

def test_exact_match(bus):
    received = []
    bus.subscribe("order.created", lambda e: received.append(e.data))
    bus.publish("order.created", {"id": 1})
    assert received == [{"id": 1}]

def test_no_match(bus):
    received = []
    bus.subscribe("order.created", lambda e: received.append(e))
    count = bus.publish("order.deleted")
    assert received == [] and count == 0

def test_multiple_handlers(bus):
    calls = []
    bus.subscribe("x", lambda e: calls.append("a"))
    bus.subscribe("x", lambda e: calls.append("b"))
    bus.publish("x")
    assert sorted(calls) == ["a", "b"]


# ── Wildcards ─────────────────────────────────────────────────────────────────

def test_single_wildcard(bus):
    hits = []
    bus.subscribe("user.*", lambda e: hits.append(e.topic))
    bus.publish("user.created")
    bus.publish("user.deleted")
    bus.publish("user.profile.updated")   # should NOT match
    assert hits == ["user.created", "user.deleted"]

def test_double_wildcard(bus):
    hits = []
    bus.subscribe("user.**", lambda e: hits.append(e.topic))
    bus.publish("user.created")
    bus.publish("user.profile.updated")
    bus.publish("user.a.b.c")
    assert hits == ["user.created", "user.profile.updated", "user.a.b.c"]

def test_global_wildcard(bus):
    hits = []
    bus.subscribe("**", lambda e: hits.append(e.topic))
    bus.publish("anything")
    bus.publish("a.b.c")
    assert hits == ["anything", "a.b.c"]

def test_char_wildcard(bus):
    hits = []
    bus.subscribe("v?.done", lambda e: hits.append(e.topic))
    bus.publish("v1.done")
    bus.publish("v2.done")
    bus.publish("v10.done")   # two chars — no match
    assert hits == ["v1.done", "v2.done"]


# ── Unsubscribe ───────────────────────────────────────────────────────────────

def test_unsubscribe(bus):
    calls = []
    sub = bus.subscribe("ping", lambda e: calls.append(1))
    bus.publish("ping")
    bus.unsubscribe(sub)
    bus.publish("ping")
    assert calls == [1]

def test_unsubscribe_idempotent(bus):
    sub = bus.subscribe("x", lambda e: None)
    assert bus.unsubscribe(sub) is True
    assert bus.unsubscribe(sub) is False   # already gone


# ── Error policies ────────────────────────────────────────────────────────────

def test_policy_log_continues(caplog):
    bus = EventBus(error_policy=ErrorPolicy.LOG)
    second = []
    bus.subscribe("e", lambda _: (_ for _ in ()).throw(RuntimeError("boom")))
    bus.subscribe("e", lambda ev: second.append(ev))
    count = bus.publish("e")
    assert count == 2 and len(second) == 1

def test_policy_raise():
    bus = EventBus(error_policy=ErrorPolicy.RAISE)
    bus.subscribe("e", lambda _: 1 / 0)
    with pytest.raises(HandlerError):
        bus.publish("e")

def test_policy_skip():
    bus = EventBus(error_policy=ErrorPolicy.SKIP)
    bus.subscribe("e", lambda _: 1 / 0)
    assert bus.publish("e") == 1   # no exception


# ── Thread safety ─────────────────────────────────────────────────────────────

def test_concurrent_publish():
    bus = EventBus()
    hits = []
    lock = threading.Lock()

    bus.subscribe("tick", lambda e: (lock.acquire(), hits.append(1), lock.release()))

    threads = [threading.Thread(target=bus.publish, args=("tick",)) for _ in range(50)]
    for t in threads: t.start()
    for t in threads: t.join()

    assert len(hits) == 50

def test_subscribe_during_publish():
    """A handler subscribing new handlers mid-publish must not deadlock."""
    bus = EventBus()
    late_calls = []

    def eager(e):
        bus.subscribe("go", lambda ev: late_calls.append(ev))

    bus.subscribe("go", eager)
    bus.publish("go")          # would deadlock with plain Lock
    bus.publish("go")          # late subscriber fires here
    assert len(late_calls) == 1

# Current: collect-then-raise (all handlers fire)
for sub in matched:
    try:
        sub.handler(event)
    except Exception as exc:
        if self._policy == ErrorPolicy.RAISE:
            errors.append((sub, exc))   # ← change this to `raise` for fail-fast

if errors:
    raise HandlerError(...) from errors[0][1]