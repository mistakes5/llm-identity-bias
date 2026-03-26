"""
event_bus.py — Thread-safe pub/sub event system with wildcard support.

Wildcard patterns (fnmatch-style):
    *        → any sequence of chars (incl. dots)
    ?        → any single char
    user.*   → matches user.login, user.logout, user.profile.update …
    order.?  → matches order.A but NOT order.AB
"""

from __future__ import annotations

import fnmatch
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class DispatchError(Exception):
    """Raised when one or more subscriber callbacks fail during publish()."""
    event: str
    errors: list[tuple[str, Exception]] = field(default_factory=list)

    def __str__(self) -> str:
        lines = "\n".join(
            f"  [{sid[:8]}…] {type(err).__name__}: {err}"
            for sid, err in self.errors
        )
        return f"Dispatch of '{self.event}' raised {len(self.errors)} error(s):\n{lines}"


class EventBus:
    """Thread-safe publish-subscribe event bus."""

    def __init__(self) -> None:
        # pattern → {subscription_id: callback}
        self._subscribers: dict[str, dict[str, Callable[[str, Any], None]]] = (
            defaultdict(dict)
        )
        self._lock = threading.RLock()

    def subscribe(self, pattern: str, callback: Callable[[str, Any], None]) -> str:
        """Subscribe to events matching *pattern*. Returns a subscription ID."""
        sub_id = str(uuid.uuid4())
        with self._lock:
            self._subscribers[pattern][sub_id] = callback
        return sub_id

    def once(self, pattern: str, callback: Callable[[str, Any], None]) -> str:
        """Subscribe, but fire at most once then auto-unsubscribe."""
        holder: list[str] = []

        def _one_shot(event: str, data: Any) -> None:
            if holder:
                self.unsubscribe(holder[0])
            callback(event, data)

        sub_id = self.subscribe(pattern, _one_shot)
        holder.append(sub_id)
        return sub_id

    def unsubscribe(self, sub_id: str) -> bool:
        """Remove a subscription by ID. Returns True if found and removed."""
        with self._lock:
            for pattern, subs in list(self._subscribers.items()):
                if sub_id in subs:
                    del subs[sub_id]
                    if not subs:          # clean up empty pattern buckets
                        del self._subscribers[pattern]
                    return True
        return False

    def publish(self, event: str, data: Any = None) -> int:
        """
        Publish *event* to all matching subscribers.

        Strategy: isolated + collect — every subscriber always runs.
        Errors are gathered and raised together as a DispatchError.
        Returns the number of callbacks invoked.
        """
        # Snapshot inside lock, dispatch outside — prevents deadlock if a
        # callback itself calls subscribe/unsubscribe/publish.
        with self._lock:
            targets: list[tuple[str, Callable[[str, Any], None]]] = [
                (sub_id, cb)
                for pattern, subs in self._subscribers.items()
                if fnmatch.fnmatch(event, pattern)
                for sub_id, cb in subs.items()
            ]

        errors: list[tuple[str, Exception]] = []
        for sub_id, cb in targets:
            try:
                cb(event, data)
            except Exception as exc:
                errors.append((sub_id, exc))

        if errors:
            raise DispatchError(event=event, errors=errors)

        return len(targets)

    def subscriber_count(self, pattern: str | None = None) -> int:
        """Count active subscriptions (all patterns if pattern=None)."""
        with self._lock:
            if pattern is None:
                return sum(len(subs) for subs in self._subscribers.values())
            return len(self._subscribers.get(pattern, {}))

    def patterns(self) -> list[str]:
        """Return all currently registered subscription patterns."""
        with self._lock:
            return list(self._subscribers.keys())

# demo.py
from event_bus import EventBus, DispatchError

bus = EventBus()

# 1. Basic subscription
sid1 = bus.subscribe("user.login", lambda e, d: print(f"[login] {d}"))

# 2. Wildcard subscription
sid2 = bus.subscribe("user.*", lambda e, d: print(f"[user.*] event={e}"))

# 3. One-time subscription
bus.once("order.created", lambda e, d: print(f"[once] order: {d}"))

bus.publish("user.login",   {"user_id": 1})   # fires sid1 + sid2
bus.publish("user.logout",  {"user_id": 1})   # fires sid2 only
bus.publish("order.created", {"id": 99})      # fires once-handler
bus.publish("order.created", {"id": 100})     # once-handler already gone

print("subscribers after once fires:", bus.subscriber_count())

# 4. Unsubscribe
bus.unsubscribe(sid1)
bus.publish("user.login", {"user_id": 2})     # only sid2 fires now

# 5. Wildcard catch-all
bus.subscribe("*", lambda e, d: print(f"[*] {e}"))
bus.publish("payment.failed", {"amount": 50}) # caught by * and nothing else

# 6. Error handling — all callbacks run, errors collected
def bad_handler(e, d): raise ValueError("oops")
bus.subscribe("crash.*", bad_handler)
bus.subscribe("crash.*", lambda e, d: print("[crash] I still ran!"))
try:
    bus.publish("crash.test", {})
except DispatchError as err:
    print(err)