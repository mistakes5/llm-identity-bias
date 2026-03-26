"""
event_bus.py — Thread-safe publish/subscribe event bus.

Supports:
  - Exact subscriptions:  subscribe("user.created", handler)
  - Wildcard patterns:    subscribe("user.*", handler)   ← one segment
                          subscribe("user.**", handler)  ← any depth
                          subscribe("**", handler)       ← everything
  - One-shot delivery:    once("order.*", handler)       ← auto-unsubscribes
  - Graceful unsubscribe: unsubscribe(sub_id) → bool
  - Bulk teardown:        clear() or clear("user.*")
"""
from __future__ import annotations

import threading
import traceback
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable

SubscriptionID = str
Handler = Callable[["Event"], None]


@dataclass(frozen=True, slots=True)
class Event:
    """Immutable envelope delivered to every matching handler."""
    name: str
    data: Any = None


@dataclass
class _Subscription:
    id: SubscriptionID
    pattern: str
    handler: Handler
    once: bool = False


class EventBus:
    """
    Thread-safe pub/sub event broker.

    Wildcard syntax (dot-delimited segments):
      *   matches exactly one segment  →  "user.*"  matches "user.created"
      **  matches zero or more segs    →  "user.**" matches "user.a.b.c"
    """

    def __init__(self) -> None:
        self._exact: dict[str, dict[SubscriptionID, _Subscription]] = defaultdict(dict)
        self._wildcards: list[_Subscription] = []
        self._index: dict[SubscriptionID, _Subscription] = {}
        self._lock = threading.RLock()   # RLock: handlers may re-enter publish()

    # ── Subscribe ─────────────────────────────────────────────────────────────

    def subscribe(self, pattern: str, handler: Handler, *, once: bool = False) -> SubscriptionID:
        sub_id = str(uuid.uuid4())
        sub = _Subscription(id=sub_id, pattern=pattern, handler=handler, once=once)
        is_wildcard = any(c in pattern for c in ("*", "?", "["))

        with self._lock:
            self._index[sub_id] = sub
            if is_wildcard:
                self._wildcards.append(sub)
            else:
                self._exact[pattern][sub_id] = sub
        return sub_id

    def once(self, pattern: str, handler: Handler) -> SubscriptionID:
        """Subscribe for exactly one delivery, then auto-cancel."""
        return self.subscribe(pattern, handler, once=True)

    # ── Unsubscribe ───────────────────────────────────────────────────────────

    def unsubscribe(self, subscription_id: SubscriptionID) -> bool:
        """Remove a subscription. Safe to call from inside a handler."""
        with self._lock:
            sub = self._index.pop(subscription_id, None)
            if sub is None:
                return False
            if any(c in sub.pattern for c in ("*", "?", "[")):
                self._wildcards = [s for s in self._wildcards if s.id != subscription_id]
            else:
                self._exact[sub.pattern].pop(subscription_id, None)
        return True

    # ── Publish ───────────────────────────────────────────────────────────────

    def publish(self, name: str, data: Any = None) -> int:
        """
        Publish an event. Returns number of handlers invoked.

        Handlers run *outside* the lock — safe to publish/subscribe from within.
        One-shots are removed *before* their handler fires.
        A failing handler is logged; delivery continues to remaining subscribers.
        """
        event = Event(name=name, data=data)
        matched: list[_Subscription] = []

        with self._lock:
            matched.extend(self._exact.get(name, {}).values())          # O(1)
            matched.extend(s for s in self._wildcards                   # O(n)
                           if self._matches(s.pattern, name))
            one_shots = [s for s in matched if s.once]

        for sub in one_shots:           # remove before firing — prevents double-delivery
            self.unsubscribe(sub.id)

        for sub in matched:             # deliver outside the lock
            try:
                sub.handler(event)
            except Exception as exc:
                _report_handler_error(sub, event, exc)

        return len(matched)

    # ── Bulk teardown ─────────────────────────────────────────────────────────

    def clear(self, pattern: str | None = None) -> int:
        """Remove all subscriptions, or only those with a specific pattern."""
        with self._lock:
            if pattern is None:
                count = len(self._index)
                self._exact.clear()
                self._wildcards.clear()
                self._index.clear()
                return count
            targets = [s for s in self._index.values() if s.pattern == pattern]

        return sum(1 for s in targets if self.unsubscribe(s.id))

    @property
    def subscriber_count(self) -> int:
        with self._lock:
            return len(self._index)

    # ── Pattern matching ──────────────────────────────────────────────────────

    def _matches(self, pattern: str, event_name: str) -> bool:
        # TODO — implement below
        raise NotImplementedError


def _report_handler_error(sub: _Subscription, event: Event, exc: Exception) -> None:
    print(f"[EventBus] handler error on '{event.name}' (sub={sub.id[:8]}…): {exc}\n"
          + traceback.format_exc())

def _matches(self, pattern: str, event_name: str) -> bool:
    # pattern:    "user.*"       "order.**"     "**"
    # event_name: "user.created" "order.a.b.c"  "anything.at.all"
    # your implementation here — 5 to 8 lines

# test_event_bus.py
from event_bus import EventBus, Event

def test_exact():
    bus = EventBus()
    log = []
    bus.subscribe("user.created", lambda e: log.append(e.name))
    bus.publish("user.created", {"id": 1})
    bus.publish("user.deleted")          # no match
    assert log == ["user.created"]

def test_wildcard_single_segment():
    bus = EventBus()
    log = []
    bus.subscribe("user.*", lambda e: log.append(e.name))
    bus.publish("user.created")
    bus.publish("user.deleted")
    bus.publish("user.profile.updated")  # should NOT match (2 segments)
    assert log == ["user.created", "user.deleted"]

def test_wildcard_deep():
    bus = EventBus()
    log = []
    bus.subscribe("user.**", lambda e: log.append(e.name))
    bus.publish("user.created")
    bus.publish("user.profile.updated")
    bus.publish("user.a.b.c.d")
    bus.publish("order.placed")          # no match
    assert len(log) == 3

def test_global_wildcard():
    bus = EventBus()
    log = []
    bus.subscribe("**", lambda e: log.append(e.name))
    bus.publish("anything")
    bus.publish("deep.nested.event")
    assert len(log) == 2

def test_once():
    bus = EventBus()
    log = []
    bus.once("order.*", lambda e: log.append(e.name))
    bus.publish("order.placed")
    bus.publish("order.cancelled")       # sub already gone
    assert log == ["order.placed"]
    assert bus.subscriber_count == 0

def test_unsubscribe():
    bus = EventBus()
    log = []
    sid = bus.subscribe("user.*", lambda e: log.append(e.name))
    bus.publish("user.created")
    bus.unsubscribe(sid)
    bus.publish("user.deleted")
    assert log == ["user.created"]

def test_handler_isolation():
    bus = EventBus()
    log = []
    bus.subscribe("x", lambda e: (_ for _ in ()).throw(RuntimeError("boom")))
    bus.subscribe("x", lambda e: log.append("ok"))
    bus.publish("x")
    assert log == ["ok"]                 # second handler still ran

def test_reentrant_publish():
    bus = EventBus()
    log = []
    def handler(e):
        if e.name == "outer":
            bus.publish("inner")         # publish inside handler
        log.append(e.name)
    bus.subscribe("outer", handler)
    bus.subscribe("inner", handler)
    bus.publish("outer")
    assert log == ["inner", "outer"]     # inner fires first, then outer resumes

if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"  ✓  {name}")
    print("\nAll tests passed.")