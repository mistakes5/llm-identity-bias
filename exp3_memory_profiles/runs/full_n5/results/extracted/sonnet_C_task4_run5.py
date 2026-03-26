"""
pubsub.py — Publish-Subscribe Event System
Supports: exact events, wildcards, one-time subs, token-based unsub.
"""

import fnmatch
import uuid
from collections import defaultdict
from typing import Any, Callable

Handler      = Callable[[str, Any], None]
ErrorHandler = Callable[[Exception, str, Any], None]


def _is_wildcard(pattern: str) -> bool:
    return "*" in pattern or "?" in pattern


class EventBus:
    """
    Usage:
        bus = EventBus()
        token = bus.subscribe("user.*", handler)
        bus.publish("user.created", {"id": 42})
        bus.unsubscribe(token)
    """

    def __init__(self, error_handler: ErrorHandler | None = None):
        self._exact:    dict[str, dict[str, Handler]] = defaultdict(dict)
        self._wildcard: list[tuple[str, str, Handler]] = []   # (pattern, token, cb)
        self._error_handler = error_handler

    # ── Subscribe ──────────────────────────────────────────────────────

    def subscribe(self, pattern: str, callback: Handler) -> str:
        """
        Subscribe to an event pattern.  Supports * and ? wildcards.
        Returns a token for later unsubscription.

        Examples:
            bus.subscribe("order.placed",  handler)   # exact
            bus.subscribe("order.*",        handler)   # all order events
            bus.subscribe("*.deleted",      handler)   # any deleted event
            bus.subscribe("*",              handler)   # every event
        """
        token = str(uuid.uuid4())
        if _is_wildcard(pattern):
            self._wildcard.append((pattern, token, callback))
        else:
            self._exact[pattern][token] = callback
        return token

    def subscribe_once(self, pattern: str, callback: Handler) -> str:
        """Subscribe for one delivery only; auto-unsubscribes after first match."""
        token_holder: list[str] = []          # mutable cell — captures token in closure

        def _one_shot(event: str, data: Any) -> None:
            self.unsubscribe(token_holder[0])
            callback(event, data)

        token = self.subscribe(pattern, _one_shot)
        token_holder.append(token)
        return token

    # ── Unsubscribe ────────────────────────────────────────────────────

    def unsubscribe(self, token: str) -> bool:
        """Remove subscription by token. Returns True if found."""
        for subscribers in self._exact.values():
            if token in subscribers:
                del subscribers[token]
                return True

        for i, (_, t, _) in enumerate(self._wildcard):
            if t == token:
                self._wildcard.pop(i)
                return True

        return False

    def unsubscribe_all(self, event: str | None = None) -> int:
        """Clear all subs (or exact subs for one event). Returns count removed."""
        if event is None:
            count = sum(len(v) for v in self._exact.values()) + len(self._wildcard)
            self._exact.clear()
            self._wildcard.clear()
            return count
        removed = len(self._exact.get(event, {}))
        self._exact.pop(event, None)
        return removed

    # ── Publish ────────────────────────────────────────────────────────

    def publish(self, event: str, data: Any = None) -> int:
        """
        Publish to all matching subscribers.
        Snapshots callbacks first — mid-delivery mutations are safe.
        Returns count of subscribers notified.
        """
        callbacks: list[Handler] = list(self._exact.get(event, {}).values())

        for pattern, _, cb in self._wildcard:
            if fnmatch.fnmatch(event, pattern):
                callbacks.append(cb)

        for cb in callbacks:
            self._invoke(cb, event, data)

        return len(callbacks)

    # ── Internal ───────────────────────────────────────────────────────

    def _invoke(self, callback: Handler, event: str, data: Any) -> None:
        try:
            callback(event, data)
        except Exception as exc:
            if self._error_handler:
                self._error_handler(exc, event, data)
            else:
                raise   # ← your error strategy lives here (see below)

    def subscriber_count(self, event: str | None = None) -> int:
        if event is not None:
            return len(self._exact.get(event, {}))
        return sum(len(v) for v in self._exact.values()) + len(self._wildcard)

    def __repr__(self) -> str:
        e = sum(len(v) for v in self._exact.values())
        return f"<EventBus exact={e} wildcard={len(self._wildcard)}>"

def publish(self, event: str, data: Any = None) -> int:
    callbacks = list(self._exact.get(event, {}).values())
    for pattern, _, cb in self._wildcard:
        if fnmatch.fnmatch(event, pattern):
            callbacks.append(cb)

    errors = []
    for cb in callbacks:
        try:
            cb(event, data)
        except Exception as exc:
            errors.append(exc)

    if errors:
        raise ExceptionGroup("pubsub delivery errors", errors)  # Python 3.11+

    return len(callbacks)

bus = EventBus()

# Exact sub
t1 = bus.subscribe("user.created", lambda e, d: print(f"[exact] {e} → {d}"))

# Wildcard sub
t2 = bus.subscribe("user.*",       lambda e, d: print(f"[wild]  {e} → {d}"))

# One-time sub
bus.subscribe_once("app.ready",    lambda e, d: print(f"[once]  {e} → {d}"))

bus.publish("user.created", {"name": "Alice"})  # hits t1 + t2
bus.publish("user.deleted", {"id": 1})          # hits t2 only
bus.publish("app.ready", "v1.0")                # fires once
bus.publish("app.ready", "v1.1")                # ← NOT delivered

bus.unsubscribe(t1)
bus.publish("user.created", {"name": "Bob"})    # only t2 fires now

print(bus)  # <EventBus exact=0 wildcard=1>