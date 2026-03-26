"""
event_bus.py — Thread-safe pub-sub with wildcard support.

fnmatch pattern syntax:
    *        matches any sequence of characters (including dots)
    ?        matches any single character
    [seq]    matches any character in seq

Examples:
    "user.*"   → "user.login", "user.logout", "user.profile.update"
    "*.error"  → "db.error", "api.error"
    "*"        → every event
"""

import fnmatch
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class Event:
    """Immutable event payload dispatched through the bus."""
    name: str
    data: Any = None

    def __repr__(self) -> str:
        return f"Event(name={self.name!r}, data={self.data!r})"


class Subscription:
    """
    Handle to an active subscription. Two ways to unsubscribe:

        sub = bus.subscribe("user.*", handler)
        sub.unsubscribe()                        # explicit

        with bus.subscribe("user.*", handler):   # auto on __exit__
            ...
    """

    def __init__(self, pattern: str, handler: Callable, token: str, bus: "EventBus") -> None:
        self.pattern = pattern
        self.handler = handler
        self.token = token
        self._bus = bus
        self._active = True

    @property
    def is_active(self) -> bool:
        return self._active

    def unsubscribe(self) -> bool:
        if self._active:
            result = self._bus.unsubscribe(self.token)
            self._active = False
            return result
        return False

    def __enter__(self) -> "Subscription":
        return self

    def __exit__(self, *_: object) -> None:
        self.unsubscribe()

    def __repr__(self) -> str:
        status = "active" if self._active else "unsubscribed"
        return f"Subscription(pattern={self.pattern!r}, {status})"


class EventBus:
    """
    Thread-safe publish-subscribe event bus.

    Args:
        on_error: Optional callback for handler exceptions.
                  Signature: on_error(exc, event, handler)
    """

    def __init__(
        self,
        on_error: Optional[Callable[[Exception, Event, Callable], None]] = None,
    ) -> None:
        # pattern -> {token -> handler}
        self._subscriptions: Dict[str, Dict[str, Callable]] = defaultdict(dict)
        # token -> pattern  (enables O(1) unsubscription)
        self._token_index: Dict[str, str] = {}
        # RLock: reentrant so handlers can safely call publish/subscribe
        self._lock = threading.RLock()
        self._on_error = on_error

    # ── Subscribe / Unsubscribe ───────────────────────────────────────────────

    def subscribe(self, pattern: str, handler: Callable[[Event], None]) -> Subscription:
        """
        Subscribe handler to every event whose name matches pattern.

        Returns a Subscription handle usable for unsubscription or as a
        context manager.
        """
        token = uuid.uuid4().hex
        with self._lock:
            self._subscriptions[pattern][token] = handler
            self._token_index[token] = pattern
        return Subscription(pattern, handler, token, self)

    def unsubscribe(self, token: str) -> bool:
        """Remove a subscription by token. Returns True if it existed."""
        with self._lock:
            if token not in self._token_index:
                return False
            pattern = self._token_index.pop(token)
            self._subscriptions[pattern].pop(token, None)
            if not self._subscriptions[pattern]:   # prune empty buckets
                del self._subscriptions[pattern]
            return True

    def unsubscribe_all(self, pattern: Optional[str] = None) -> int:
        """
        Remove all subscriptions, or only those for an exact pattern.
        Returns the number of subscriptions removed.
        """
        with self._lock:
            if pattern is not None:
                tokens = list(self._subscriptions.get(pattern, {}).keys())
                for t in tokens:
                    self._token_index.pop(t, None)
                return len(self._subscriptions.pop(pattern, {}))
            count = len(self._token_index)
            self._subscriptions.clear()
            self._token_index.clear()
            return count

    # ── Publish ───────────────────────────────────────────────────────────────

    def publish(self, name: str, data: Any = None) -> int:
        """
        Dispatch an event to all matching subscribers.

        Handlers are snapshotted under the lock, then invoked outside it —
        so handlers may safely call subscribe/publish/unsubscribe without
        deadlocking.

        Returns the number of handlers that completed without error.
        """
        event = Event(name=name, data=data)

        handlers: List[Callable] = []
        with self._lock:
            for pattern, subs in self._subscriptions.items():
                if fnmatch.fnmatch(name, pattern):
                    handlers.extend(subs.values())

        return sum(1 for h in handlers if self._invoke_handler(h, event))

    def _invoke_handler(self, handler: Callable[[Event], None], event: Event) -> bool:
        """
        Invoke one handler for the given event.

        TODO — implement your error-handling strategy here.

        This method is the seam between "dispatch" and "resilience."
        Return True on success, False on failure. Four strategies:

        A) Silent swallow — resilient, one bad handler never blocks others:
              try:
                  handler(event)
                  return True
              except Exception:
                  return False

        B) Fail-fast — immediate feedback, but skips remaining handlers:
              handler(event)
              return True

        C) Error callback — caller controls the policy (log, alert, re-raise):
              try:
                  handler(event)
                  return True
              except Exception as exc:
                  if self._on_error:
                      self._on_error(exc, event, handler)
                  return False

        D) Collect & raise (Python 3.11+) — all handlers run, all errors surface.
             Requires restructuring publish() to accumulate into ExceptionGroup.
        """
        # ── your implementation goes here ──────────────────────────────
        pass

    # ── Introspection ─────────────────────────────────────────────────────────

    def subscriber_count(self, pattern: Optional[str] = None) -> int:
        """Total subscriptions, or subscriptions for one exact pattern."""
        with self._lock:
            if pattern is not None:
                return len(self._subscriptions.get(pattern, {}))
            return sum(len(subs) for subs in self._subscriptions.values())

    def patterns(self) -> List[str]:
        """Snapshot of all registered patterns."""
        with self._lock:
            return list(self._subscriptions.keys())

    def __repr__(self) -> str:
        return f"EventBus({self.subscriber_count()} subs across {len(self.patterns())} patterns)"


# ── Demo ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    bus = EventBus()

    # Exact subscription via context manager
    with bus.subscribe("user.login", lambda e: print(f"[login]  {e.data}")):
        bus.publish("user.login",  {"user_id": 42, "ip": "10.0.0.1"})
        bus.publish("user.logout", {"user_id": 42})    # not matched

    bus.publish("user.login", "no subscribers here")   # auto-removed

    # Wildcard: all user events
    sub = bus.subscribe("user.*", lambda e: print(f"[user.*] {e.name}: {e.data}"))
    bus.publish("user.login",   {"user_id": 7})
    bus.publish("user.logout",  {"user_id": 7})
    bus.publish("order.placed", {"order_id": 99})      # not matched

    # Wildcard: catch everything (audit log)
    audit = bus.subscribe("*", lambda e: print(f"[audit]  {e.name}"))
    bus.publish("order.placed",   {"order_id": 100})
    bus.publish("payment.failed", {"amount": 59.99})

    sub.unsubscribe()
    audit.unsubscribe()

    print(f"\nActive subs: {bus.subscriber_count()}")
    print(f"Patterns:    {bus.patterns()}")