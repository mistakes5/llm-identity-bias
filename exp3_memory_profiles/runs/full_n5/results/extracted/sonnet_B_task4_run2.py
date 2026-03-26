"""
Publish-Subscribe Event System
================================
Thread-safe pub-sub with wildcard pattern matching.

Wildcard syntax (fnmatch):
  *       matches everything              e.g. "user.*" → "user.login", "user.logout"
  ?       matches any single character    e.g. "order.??" → "order.US", "order.CA"
  [seq]   matches any character in seq    e.g. "server.[AB]" → "server.A", "server.B"
"""

from __future__ import annotations

import fnmatch
import threading
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Optional


@dataclass
class Subscription:
    """A single registered listener."""
    id: str
    pattern: str
    callback: Callable[[str, Any], None]


class EventSystem:
    """
    Thread-safe publish-subscribe bus with wildcard subscriptions.

    Args:
        error_handler: Optional callable(sub, event, data, exc) invoked when
                       a subscriber raises. Defaults to _handle_callback_error.
    """

    def __init__(self, error_handler: Optional[Callable] = None) -> None:
        self._subscriptions: dict[str, Subscription] = {}
        self._lock = threading.RLock()          # RLock: safe for re-entrant calls
        self._error_handler = error_handler or self._handle_callback_error

    # ── Subscribe ─────────────────────────────────────────────────────────────

    def subscribe(self, pattern: str, callback: Callable[[str, Any], None]) -> str:
        """
        Register a callback for all events matching pattern.

        Returns:
            subscription_id — pass to unsubscribe() to deregister.
        """
        sub = Subscription(id=str(uuid.uuid4()), pattern=pattern, callback=callback)
        with self._lock:
            self._subscriptions[sub.id] = sub
        return sub.id

    def subscribe_once(self, pattern: str, callback: Callable[[str, Any], None]) -> str:
        """Like subscribe(), but auto-unsubscribes after the first match."""
        holder: list[str] = []          # list lets the closure mutate after assignment

        def _one_shot(event: str, data: Any) -> None:
            self.unsubscribe(holder[0])
            callback(event, data)

        sub_id = self.subscribe(pattern, _one_shot)
        holder.append(sub_id)
        return sub_id

    # ── Unsubscribe ───────────────────────────────────────────────────────────

    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove a subscription by ID. Returns True if it existed."""
        with self._lock:
            return self._subscriptions.pop(subscription_id, None) is not None

    def clear(self, pattern: Optional[str] = None) -> int:
        """
        Remove subscriptions in bulk.

        Args:
            pattern: If given, only exact-pattern matches are removed.
                     If None, all subscriptions are cleared.

        Returns:
            Number of subscriptions removed.
        """
        with self._lock:
            if pattern is None:
                count = len(self._subscriptions)
                self._subscriptions.clear()
                return count

            targets = [
                sid for sid, sub in self._subscriptions.items()
                if sub.pattern == pattern
            ]
            for sid in targets:
                del self._subscriptions[sid]
            return len(targets)

    # ── Publish ───────────────────────────────────────────────────────────────

    def publish(self, event: str, data: Any = None) -> int:
        """
        Emit event to all matching subscribers (synchronous, registration order).

        Returns:
            Number of subscribers notified.
        """
        with self._lock:
            matches = [
                sub for sub in self._subscriptions.values()
                if fnmatch.fnmatch(event, sub.pattern)
            ]

        for sub in matches:
            try:
                sub.callback(event, data)
            except Exception as exc:
                self._error_handler(sub, event, data, exc)

        return len(matches)

    # ── Introspection ─────────────────────────────────────────────────────────

    def listener_count(self, event: Optional[str] = None) -> int:
        """Subscriptions that would fire for event (or total if event is None)."""
        with self._lock:
            if event is None:
                return len(self._subscriptions)
            return sum(
                1 for sub in self._subscriptions.values()
                if fnmatch.fnmatch(event, sub.pattern)
            )

    def active_patterns(self) -> list[str]:
        """Snapshot of all currently registered patterns."""
        with self._lock:
            return [sub.pattern for sub in self._subscriptions.values()]

    # ── Error handling — YOUR TURN ────────────────────────────────────────────

    def _handle_callback_error(
        self,
        sub: Subscription,
        event: str,
        data: Any,
        exc: Exception,
    ) -> None:
        """
        TODO: implement your error handling strategy here (5-10 lines).
        See example.py for trade-off guidance.
        """
        raise NotImplementedError("See example.py")

"""Examples covering every feature + error handler options."""

import logging
from event_system import EventSystem

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)


# ── 1. Basic subscribe / publish / unsubscribe ────────────────────────────────

bus = EventSystem(error_handler=lambda sub, ev, data, exc:
    log.error("Subscriber %s failed on %r: %s", sub.id[:8], ev, exc))

sub_id = bus.subscribe("user.login", lambda ev, data: print(f"  Login: {data}"))
bus.publish("user.login", {"user_id": 42})   # ✓ fires
bus.unsubscribe(sub_id)
bus.publish("user.login", {"user_id": 99})   # silent — no subscribers


# ── 2. Wildcard patterns ──────────────────────────────────────────────────────

bus.subscribe("order.*",   lambda ev, d: print(f"  Order event   → {ev}: {d}"))
bus.subscribe("*.error",   lambda ev, d: print(f"  Error event   → {ev}: {d}"))
bus.subscribe("server.[AB]", lambda ev, d: print(f"  Server A or B → {ev}: {d}"))

bus.publish("order.created",  {"id": 1})     # hits "order.*"
bus.publish("order.shipped",  {"id": 1})     # hits "order.*"
bus.publish("db.error",       {"code": 500}) # hits "*.error"
bus.publish("server.A",       {})            # hits "server.[AB]"
bus.publish("server.C",       {})            # no match


# ── 3. subscribe_once ─────────────────────────────────────────────────────────

bus.subscribe_once("app.ready", lambda ev, d: print("  App is ready (fires once)"))
bus.publish("app.ready")   # fires
bus.publish("app.ready")   # silent — already removed


# ── 4. Introspection ──────────────────────────────────────────────────────────

print(f"\n  Active listeners for 'order.created': {bus.listener_count('order.created')}")
print(f"  Total subscriptions: {bus.listener_count()}")
print(f"  Patterns: {bus.active_patterns()}\n")


# ── 5. Error handler options — pick ONE ──────────────────────────────────────
#
# Option A: Log and continue (resilient — other subscribers still run)
#
#   def log_and_continue(sub, event, data, exc):
#       log.error("[%s] subscriber error on %r: %s", sub.id[:8], event, exc)
#
#
# Option B: Fail-fast (debugging — stops at the first broken subscriber)
#
#   def fail_fast(sub, event, data, exc):
#       raise RuntimeError(f"Subscriber {sub.id} failed on {event!r}") from exc
#
#
# Option C: Collect errors (auditing — publish returns after calling all callbacks)
#
#   errors = []
#   def collect(sub, event, data, exc):
#       errors.append({"sub_id": sub.id, "event": event, "exc": exc})
#   # Check errors after bus.publish(...)
#
#
# Option D: Dead-letter queue (production — failed events are retried later)
#
#   dead_letters = []
#   def dead_letter(sub, event, data, exc):
#       log.warning("Dead-lettering %r from sub %s", event, sub.id[:8])
#       dead_letters.append({"pattern": sub.pattern, "event": event, "data": data})
#
# ─────────────────────────────────────────────────────────────────────────────

safe_bus = EventSystem(
    error_handler=lambda sub, ev, data, exc:
        log.error("[%s] error on %r: %s", sub.id[:8], ev, exc)
)
safe_bus.subscribe("pay.*", lambda ev, d: 1 / 0)           # raises ZeroDivisionError
safe_bus.subscribe("pay.*", lambda ev, d: print("  Audit log still runs ✓"))
safe_bus.publish("pay.captured", {"amount": 99.00})