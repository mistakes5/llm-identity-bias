"""
Publish-Subscribe Event Bus
============================
Supports exact names, wildcard patterns (fnmatch), one-shot subs, thread safety.

Wildcard examples
-----------------
  "user.*"       -> user.created, user.deleted
  "*.error"      -> db.error, auth.error
  "*"            -> every event
  "order.*.paid" -> order.retail.paid, order.wholesale.paid
"""

from __future__ import annotations

import fnmatch
import logging
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

EventCallback = Callable[[str, Any], None]   # fn(event_name, data) -> None


# ── internal record ───────────────────────────────────────

@dataclass
class _Subscription:
    id: str
    pattern: str
    callback: EventCallback
    once: bool = False          # auto-remove after first dispatch


# ── public result ─────────────────────────────────────────

@dataclass
class PublishResult:
    event: str
    notified: int
    errors: list[Exception] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


# ── core bus ──────────────────────────────────────────────

class EventBus:
    """Thread-safe publish-subscribe event bus with wildcard support."""

    def __init__(self, error_handler: Callable | None = None):
        self._subscriptions: dict[str, _Subscription] = {}
        self._lock = threading.RLock()
        self._error_handler = error_handler or self._default_error_handler

    # ── subscribe ──────────────────────────────

    def subscribe(self, pattern: str, callback: EventCallback) -> str:
        """Subscribe to all events matching *pattern*. Returns subscription ID."""
        sub_id = str(uuid.uuid4())
        with self._lock:
            self._subscriptions[sub_id] = _Subscription(
                id=sub_id, pattern=pattern, callback=callback
            )
        return sub_id

    def subscribe_once(self, pattern: str, callback: EventCallback) -> str:
        """Like subscribe() but auto-unsubscribes after the first match."""
        sub_id = str(uuid.uuid4())
        with self._lock:
            self._subscriptions[sub_id] = _Subscription(
                id=sub_id, pattern=pattern, callback=callback, once=True
            )
        return sub_id

    # ── unsubscribe ────────────────────────────

    def unsubscribe(self, subscription_id: str) -> bool:
        """Cancel a subscription. Returns True if it existed."""
        with self._lock:
            removed = self._subscriptions.pop(subscription_id, None)
        return removed is not None

    def unsubscribe_all(self, pattern: str | None = None) -> int:
        """Remove all subs, or only those with an exact pattern match."""
        with self._lock:
            if pattern is None:
                count = len(self._subscriptions)
                self._subscriptions.clear()
            else:
                ids = [sid for sid, s in self._subscriptions.items()
                       if s.pattern == pattern]
                for sid in ids:
                    del self._subscriptions[sid]
                count = len(ids)
        return count

    # ── publish ────────────────────────────────

    def publish(self, event: str, data: Any = None) -> PublishResult:
        """
        Dispatch *event* to every matching subscriber.
        Returns a PublishResult with notified count and any errors.
        """
        # Snapshot + remove once-subs under the lock
        with self._lock:
            matching, once_ids = [], []
            for sub in self._subscriptions.values():
                if fnmatch.fnmatch(event, sub.pattern):
                    matching.append(sub)
                    if sub.once:
                        once_ids.append(sub.id)
            for sid in once_ids:
                del self._subscriptions[sid]

        # Dispatch outside lock so callbacks can safely (un)subscribe
        notified, errors = 0, []
        for sub in matching:
            try:
                sub.callback(event, data)
                notified += 1
            except Exception as exc:
                errors.append(exc)
                self._error_handler(exc, sub, event, data)

        return PublishResult(event=event, notified=notified, errors=errors)

    # ── introspection ──────────────────────────

    def listener_count(self, event: str | None = None) -> int:
        """Count subs that match *event*, or total count if event is None."""
        with self._lock:
            if event is None:
                return len(self._subscriptions)
            return sum(
                1 for s in self._subscriptions.values()
                if fnmatch.fnmatch(event, s.pattern)
            )

    # ── error handling ─────────────────────────

    def _default_error_handler(
        self,
        exc: Exception,
        sub: _Subscription,
        event: str,
        data: Any,
    ) -> None:
        """
        TODO — implement your strategy here (5-10 lines).

        Option A  Silent log (isolation)       — log + continue dispatching
        Option B  Fail-fast                    — raise exc immediately
        Option C  Collect + raise at the end   — AggregateError after all run
        Option D  Dead-letter queue            — append to self._dead_letters
        """
        logger.error(
            "Subscriber error  event=%r  pattern=%r  id=%s",
            event, sub.pattern, sub.id, exc_info=exc,
        )

bus = EventBus()

# ── exact subscription ─────────────────────────────────────
def on_login(event, data):
    print(f"[{event}] user={data['user']}")

sid = bus.subscribe("user.login", on_login)
bus.publish("user.login", {"user": "alice"})   # fires
bus.publish("user.logout", {"user": "alice"})  # does NOT fire

# ── wildcard subscription ──────────────────────────────────
def on_any_user(event, data):
    print(f"[{event}] -> {data}")

bus.subscribe("user.*", on_any_user)
bus.publish("user.created",  {"user": "bob"})  # fires
bus.publish("user.deleted",  {"user": "bob"})  # fires
bus.publish("order.created", {"id": 42})       # does NOT fire

# ── one-shot subscription ──────────────────────────────────
bus.subscribe_once("app.ready", lambda e, d: print("app is ready!"))
bus.publish("app.ready")   # fires, then auto-unsubscribes
bus.publish("app.ready")   # silent — already removed

# ── unsubscribe ────────────────────────────────────────────
bus.unsubscribe(sid)       # cancel the user.login handler
print(bus.listener_count("user.login"))  # 0

# ── custom error handler (inject at construction) ──────────
def my_error_handler(exc, sub, event, data):
    print(f"ERROR in {sub.pattern!r}: {exc}")
    # option B: re-raise to halt remaining callbacks
    raise exc

bus2 = EventBus(error_handler=my_error_handler)