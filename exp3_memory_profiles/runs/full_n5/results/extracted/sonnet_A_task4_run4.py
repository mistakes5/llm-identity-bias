"""
event_bus.py — Thread-safe publish-subscribe event bus with wildcard support.

Wildcard rules (dot-separated event namespaces):
  *    matches exactly one segment    e.g. "user.*"    → "user.created"
  **   matches zero or more segments  e.g. "order.**"  → "order.item.shipped"
  literal                             e.g. "ping"      → "ping" only
"""

from __future__ import annotations

import asyncio
import re
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

Handler = Callable[[str, Any], None]


# ── Pattern compilation ────────────────────────────────────────────────────────

def _compile_pattern(pattern: str) -> re.Pattern[str]:
    """Convert a dot-namespaced wildcard pattern into a compiled regex."""
    parts: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern[i : i + 2] == "**":
            parts.append(".*")
            i += 2
        elif pattern[i] == "*":
            parts.append(r"[^.]+")   # one segment, no dots
            i += 1
        elif pattern[i] == ".":
            parts.append(r"\.")
            i += 1
        else:
            parts.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(parts) + "$")


# ── Subscription token ─────────────────────────────────────────────────────────

@dataclass
class Subscription:
    """Opaque token for one active subscription. Call .cancel() to remove it."""

    id: str
    pattern: str
    handler: Handler
    _bus: "EventBus" = field(repr=False, compare=False)

    def cancel(self) -> bool:
        return self._bus.unsubscribe(self)

    def __hash__(self) -> int:
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Subscription) and self.id == other.id


# ── Core event bus ─────────────────────────────────────────────────────────────

class EventBus:
    """
    Thread-safe publish-subscribe event bus.

    Quick start::

        bus = EventBus()
        sub = bus.subscribe("user.*", lambda ev, data: print(ev, data))
        bus.publish("user.created", {"id": 42})  # fires the handler
        sub.cancel()                             # unsubscribe
    """

    def __init__(self) -> None:
        self._subscriptions: dict[str, set[Subscription]] = defaultdict(set)
        self._pattern_cache: dict[str, re.Pattern[str]] = {}
        self._lock = threading.RLock()

    # ── Subscribe / Unsubscribe ────────────────────────────────────────────────

    def subscribe(self, pattern: str, handler: Handler) -> Subscription:
        """Attach *handler* to every event matching *pattern*."""
        sub = Subscription(
            id=str(uuid.uuid4()),
            pattern=pattern,
            handler=handler,
            _bus=self,
        )
        with self._lock:
            self._subscriptions[pattern].add(sub)
            self._pattern_cache.setdefault(pattern, _compile_pattern(pattern))
        return sub

    def unsubscribe(self, subscription: Subscription) -> bool:
        """Remove *subscription*. Returns True if it existed."""
        with self._lock:
            bucket = self._subscriptions.get(subscription.pattern)
            if not bucket or subscription not in bucket:
                return False
            bucket.discard(subscription)
            if not bucket:
                del self._subscriptions[subscription.pattern]
                self._pattern_cache.pop(subscription.pattern, None)
            return True

    # ── Publish ────────────────────────────────────────────────────────────────

    def publish(self, event: str, data: Any = None) -> int:
        """Publish *event* synchronously. Returns the number of handlers invoked."""
        handlers = self._collect_handlers(event)
        for handler in handlers:
            self._invoke(handler, event, data)
        return len(handlers)

    async def publish_async(self, event: str, data: Any = None) -> int:
        """Async variant — awaits coroutine handlers inline."""
        handlers = self._collect_handlers(event)
        for handler in handlers:
            result = handler(event, data)
            if asyncio.iscoroutine(result):
                await result
        return len(handlers)

    # ── Utility ────────────────────────────────────────────────────────────────

    def clear(self, pattern: str | None = None) -> None:
        """Remove all subscriptions, or only those matching *pattern*."""
        with self._lock:
            if pattern is None:
                self._subscriptions.clear()
                self._pattern_cache.clear()
            else:
                self._subscriptions.pop(pattern, None)
                self._pattern_cache.pop(pattern, None)

    @property
    def subscription_count(self) -> int:
        with self._lock:
            return sum(len(s) for s in self._subscriptions.values())

    def patterns(self) -> list[str]:
        with self._lock:
            return list(self._subscriptions.keys())

    # ── Internals ──────────────────────────────────────────────────────────────

    def _collect_handlers(self, event: str) -> list[Handler]:
        """Snapshot subscriptions under lock, then match outside the lock."""
        with self._lock:
            items = list(self._subscriptions.items())
            cache = dict(self._pattern_cache)

        matched: list[Handler] = []
        for pattern, subs in items:
            regex = cache.get(pattern) or _compile_pattern(pattern)
            if regex.fullmatch(event):
                matched.extend(sub.handler for sub in subs)
        return matched

    def _invoke(self, handler: Handler, event: str, data: Any) -> None:
        # ┌──────────────────────────────────────────────────────────────┐
        # │  TODO — your error-handling policy lives here.               │
        # │  See demo.py for a description of the four options.          │
        # └──────────────────────────────────────────────────────────────┘
        raise NotImplementedError("implement _invoke — see demo.py")

"""
demo.py — EventBus usage and the _invoke decision you need to make.
"""

import logging
from event_bus import EventBus

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s  %(message)s")
log = logging.getLogger("bus")


# ── Four error-handling strategies for EventBus._invoke ───────────────────────
#
# The _invoke method decides what happens when a subscriber raises an exception.
# This is a real architectural trade-off with no universally correct answer.
#
# Option A — Silent isolation (most common in production buses)
#   Catch all exceptions, log them, continue to the next handler.
#   Pro: one bad subscriber never breaks others.
#   Con: failures are invisible unless you watch the logs carefully.
#
# Option B — Fail-fast (good for development / test environments)
#   Let exceptions propagate; publish() itself raises.
#   Pro: bugs surface immediately.
#   Con: one bad subscriber silently kills the rest.
#
# Option C — Error event (observer-of-observers pattern)
#   Catch exceptions and re-publish them as a special "bus.error" event,
#   letting callers subscribe to errors like any other event.
#   Pro: composable error handling without coupling to logging.
#   Con: risk of infinite recursion if the error handler also raises.
#
# Option D — Circuit breaker
#   Track consecutive failures per handler. After N failures, auto-remove
#   the subscription and optionally publish a "bus.circuit_open" event.
#   Pro: self-healing; a broken dependency doesn't slow the whole bus forever.
#   Con: more state to manage; handler removal is surprising to the subscriber.
#
# ─────────────────────────────────────────────────────────────────────────────
# YOUR TASK: pick one strategy and implement _invoke in a subclass below.
# Aim for 5–10 lines. The class skeleton is ready for you.


class MyEventBus(EventBus):
    """
    Subclass EventBus and implement _invoke with your chosen error strategy.

    Example signature:
        def _invoke(self, handler, event, data):
            ...
    """

    def _invoke(self, handler, event, data):
        # ← implement your strategy here (5-10 lines)
        pass


# ── Demo — runs once _invoke is implemented ───────────────────────────────────

def run_demo():
    bus = MyEventBus()

    # ── 1. Basic subscription and publish ─────────────────────────────────────
    print("\n── 1. Basic ──")
    sub = bus.subscribe("ping", lambda ev, data: print(f"  pong! data={data}"))
    bus.publish("ping", "hello")        # fires
    bus.publish("pong", "ignored")      # no match → 0 handlers

    # ── 2. Wildcard: single segment (*) ───────────────────────────────────────
    print("\n── 2. Single-segment wildcard ──")
    bus.subscribe("user.*", lambda ev, data: print(f"  user event: {ev}  id={data['id']}"))
    bus.publish("user.created", {"id": 1})   # ✓
    bus.publish("user.deleted", {"id": 2})   # ✓
    bus.publish("user.profile.updated", {})  # ✗ — crosses a dot boundary

    # ── 3. Wildcard: multi-segment (**) ───────────────────────────────────────
    print("\n── 3. Multi-segment wildcard ──")
    bus.subscribe("order.**", lambda ev, data: print(f"  order tree: {ev}"))
    bus.publish("order.placed", {})           # ✓
    bus.publish("order.item.shipped", {})     # ✓  (crosses dot boundary)
    bus.publish("order.item.label.printed", {}) # ✓

    # ── 4. Multiple handlers on one event ─────────────────────────────────────
    print("\n── 4. Fan-out ──")
    bus.subscribe("payment.completed", lambda ev, d: print(f"  email receipt  → {d['email']}"))
    bus.subscribe("payment.completed", lambda ev, d: print(f"  update ledger  → ${d['amount']}"))
    bus.subscribe("payment.**",        lambda ev, d: print(f"  audit log      → {ev}"))
    count = bus.publish("payment.completed", {"email": "a@b.com", "amount": 99.0})
    print(f"  {count} handlers invoked")

    # ── 5. Unsubscribe ────────────────────────────────────────────────────────
    print("\n── 5. Unsubscribe ──")
    once_sub = bus.subscribe("once", lambda ev, _: print("  fired once"))
    bus.publish("once")          # fires
    once_sub.cancel()
    bus.publish("once")          # silent — no handlers

    # ── 6. Subscription count and clear ───────────────────────────────────────
    print(f"\n── 6. Housekeeping ──")
    print(f"  active subscriptions: {bus.subscription_count}")
    bus.clear()
    print(f"  after clear(): {bus.subscription_count}")

    # ── 7. Faulty handler ─────────────────────────────────────────────────────
    print("\n── 7. Faulty handler ──")
    bus.subscribe("crash", lambda ev, _: (_ for _ in ()).throw(RuntimeError("boom")))
    bus.subscribe("crash", lambda ev, _: print("  second handler — should still run"))
    bus.publish("crash")   # behaviour depends on your _invoke strategy


if __name__ == "__main__":
    run_demo()

def _invoke(self, handler, event, data):
    # your ~5-10 lines here
    ...