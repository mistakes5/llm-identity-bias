"""
Thread-safe publish/subscribe event bus with wildcard pattern matching.

Pattern syntax
--------------
*       Exactly one segment (no dots).   "order.*"  → order.created, order.deleted
**      Any chars, including dots.       "order.**" → order.a, order.a.b.c
?       One non-dot character.           "order.?et"→ order.get, order.set
Exact   Literal match.                  "order.created"

Note: "**.failed" matches "order.failed" and "payment.retry.failed"
      but NOT bare "failed" — it requires at least one dot prefix.
      Use "**" alone to match everything.
"""
from __future__ import annotations

import logging
import re
import threading
import uuid
import weakref
from dataclasses import dataclass
from typing import Any, Callable

log = logging.getLogger(__name__)


# ── Domain types ──────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class Event:
    """Immutable event envelope. `data` is entirely caller-defined."""
    name: str
    data: Any = None


class DispatchError(Exception):
    """Carries all handler failures from a single publish() call."""
    def __init__(
        self,
        event: Event,
        failures: list[tuple[Callable[..., Any], BaseException]],
    ) -> None:
        self.event = event
        self.failures = failures
        detail = "\n".join(f"  {fn.__qualname__}: {err!r}" for fn, err in failures)
        super().__init__(f"{len(failures)} handler(s) raised for {event.name!r}:\n{detail}")


# ── Pattern compiler ──────────────────────────────────────────────────────────

def _compile_pattern(pattern: str) -> re.Pattern[str]:
    """
    Compile a glob-style event pattern to an anchored regex.

    Splits on '**' (→ '.*'), then translates '*' (→ '[^.]+') and
    '?' (→ '[^.]') within each non-** segment.
    """
    def _escape_segment(s: str) -> str:
        buf: list[str] = []
        for ch in s:
            if ch == "*":   buf.append(r"[^.]+")
            elif ch == "?": buf.append(r"[^.]")
            elif ch == ".": buf.append(r"\.")
            else:           buf.append(re.escape(ch))
        return "".join(buf)

    return re.compile(
        r"\A" + r".*".join(_escape_segment(p) for p in pattern.split("**")) + r"\Z"
    )


# ── Subscription handle ───────────────────────────────────────────────────────

class Subscription:
    """
    Opaque handle returned by EventBus.subscribe() / EventBus.once().
    Call .cancel() or use as a context manager for scoped lifetime.
    """
    __slots__ = ("_id", "pattern", "_handler", "_bus_ref")

    def __init__(self, pattern: str, handler: Callable[[Event], None], bus: "EventBus") -> None:
        self._id: str = uuid.uuid4().hex
        self.pattern: str = pattern
        self._handler = handler
        self._bus_ref: weakref.ref["EventBus"] = weakref.ref(bus)

    def cancel(self) -> bool:
        bus = self._bus_ref()
        return bus.unsubscribe(self) if bus is not None else False

    def __enter__(self) -> "Subscription": return self
    def __exit__(self, *_: object) -> None: self.cancel()
    def __repr__(self) -> str: return f"<Subscription pattern={self.pattern!r} id={self._id[:8]}>"


# ── Event bus ─────────────────────────────────────────────────────────────────

class EventBus:
    """
    Thread-safe pub/sub event bus.

        bus = EventBus()
        sub = bus.subscribe("order.*", handler)
        bus.publish("order.created", {"id": 42})  # → 1
        sub.cancel()
    """

    def __init__(self) -> None:
        self._subs: dict[str, tuple[Subscription, re.Pattern[str]]] = {}
        self._lock = threading.RLock()

    def subscribe(self, pattern: str, handler: Callable[[Event], None]) -> Subscription:
        """Register handler for events matching pattern. Pattern compiled once, not per-dispatch."""
        compiled = _compile_pattern(pattern)
        sub = Subscription(pattern, handler, self)
        with self._lock:
            self._subs[sub._id] = (sub, compiled)
        return sub

    def unsubscribe(self, subscription: Subscription) -> bool:
        with self._lock:
            return self._subs.pop(subscription._id, None) is not None

    def once(self, pattern: str, handler: Callable[[Event], None]) -> Subscription:
        """Fire-once: auto-cancels before the handler is called (safe for re-entrant publish)."""
        sub_holder: list[Subscription] = []

        def _one_shot(event: Event) -> None:
            sub_holder[0].cancel()
            handler(event)

        sub = self.subscribe(pattern, _one_shot)
        sub_holder.append(sub)
        return sub

    def publish(self, event_name: str, data: Any = None) -> int:
        """
        Dispatch to all matching subscribers.

        Snapshots subscribers under the lock, invokes handlers outside it —
        prevents deadlocks when a handler calls publish() re-entrantly.

        Returns count of handlers that completed without raising.
        Failures are routed to _handle_failures(); implement that method.
        """
        event = Event(name=event_name, data=data)

        with self._lock:
            matching = [sub for sub, rx in self._subs.values() if rx.match(event_name)]

        failures: list[tuple[Callable[..., Any], BaseException]] = []
        for sub in matching:
            try:
                sub._handler(event)
            except Exception as exc:
                failures.append((sub._handler, exc))

        if failures:
            self._handle_failures(event, failures)

        return len(matching) - len(failures)

    def clear(self, pattern: str | None = None) -> int:
        """Remove all subscriptions, or only those with the given pattern string."""
        with self._lock:
            if pattern is None:
                count = len(self._subs)
                self._subs.clear()
                return count
            to_drop = [sid for sid, (sub, _) in self._subs.items() if sub.pattern == pattern]
            for sid in to_drop:
                del self._subs[sid]
            return len(to_drop)

    @property
    def subscription_count(self) -> int:
        with self._lock:
            return len(self._subs)

    # ── Your contribution ─────────────────────────────────────────────────────

    def _handle_failures(
        self,
        event: Event,
        failures: list[tuple[Callable[..., Any], BaseException]],
    ) -> None:
        """
        Called when one or more handlers raised during publish().

        Four options — pick one:

        A) Log-and-continue  (fire-and-forget, async pipelines, backpressure-tolerant)
            for fn, exc in failures:
                log.exception("handler %r failed for %r", fn.__qualname__, event.name, exc_info=exc)

        B) Collect-and-raise  (transactional, upstream caller handles)
            raise DispatchError(event, failures)

        C) Dead-letter queue  (defer inspection, no runtime disruption)
            self._dlq.append((event, failures))

        D) Metrics + structured log  (production observability, silent on caller)
            for fn, exc in failures:
                log.error("dispatch_failure", extra={"event": event.name, "handler": fn.__qualname__})
        """
        raise NotImplementedError("Implement _handle_failures() — see docstring above.")

from event_bus import EventBus, Event

class LoggingBus(EventBus):
    def _handle_failures(self, event, failures):
        for fn, exc in failures:
            log.exception("handler %r failed for %r", fn.__qualname__, event.name, exc_info=exc)

bus = LoggingBus()

# Exact match
bus.subscribe("order.created", lambda e: print(f"exact: {e.data}"))

# Single-segment wildcard
bus.subscribe("order.*", lambda e: print(f"order.*: {e.name}"))

# Multi-segment wildcard
bus.subscribe("order.**", lambda e: print(f"order.**: {e.name}"))

# Global catch-all
bus.subscribe("**", lambda e: print(f"all: {e.name}"))

# Fire-once
bus.once("order.created", lambda e: print("fires once only"))

# Context-manager scope
with bus.subscribe("payment.*", lambda e: ...):
    bus.publish("payment.failed", {"amount": 99})
# ↑ auto-cancelled here

bus.publish("order.created", {"id": 1})
# → exact: {'id': 1}
# → order.*: order.created
# → order.**: order.created
# → all: order.created
# → fires once only

bus.publish("order.line.item.added")
# → order.**: order.line.item.added  (crosses dots)
# → all: order.line.item.added