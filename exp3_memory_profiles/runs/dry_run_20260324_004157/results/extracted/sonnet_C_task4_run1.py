"""
Publish-Subscribe Event System
================================
Supports exact-match and wildcard subscriptions, thread-safe dispatch,
and token-based unsubscription.

Wildcard rules (fnmatch-style):
  *   matches any characters (e.g. "user.*" matches "user.login")
  **  also matches dots/segments  (e.g. "**" = catch-all)
  ?   matches exactly one character
"""

import fnmatch
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

Handler = Callable[[str, Any], None]


# ── Subscription token ────────────────────────────────────────────────────────

@dataclass
class SubscriptionToken:
    """Opaque handle returned by EventBus.subscribe(). Call .cancel() to remove."""
    id: str
    pattern: str
    _bus: "EventBus" = field(repr=False)
    _cancelled: bool = field(default=False, repr=False)

    def cancel(self) -> None:
        """Unsubscribe. Safe to call multiple times."""
        if not self._cancelled:
            self._bus.unsubscribe(self)
            self._cancelled = True

    @property
    def active(self) -> bool:
        return not self._cancelled


# ── Internal record ───────────────────────────────────────────────────────────

@dataclass
class _Subscription:
    token: SubscriptionToken
    handler: Handler


# ── EventBus ──────────────────────────────────────────────────────────────────

class EventBus:
    """Thread-safe publish-subscribe bus with fnmatch wildcard support."""

    def __init__(self) -> None:
        self._lock = threading.RLock()          # RLock = reentrant, handler-safe
        self._subscriptions: list[_Subscription] = []

    def subscribe(self, pattern: str, handler: Handler) -> SubscriptionToken:
        """
        Register handler for events matching pattern.

        Args:
            pattern: Exact name ("user.login") or glob ("user.*", "**").
            handler: Called as handler(event_name, data) on each match.

        Returns:
            SubscriptionToken — call .cancel() to unsubscribe.
        """
        token = SubscriptionToken(id=str(uuid.uuid4()), pattern=pattern, _bus=self)
        with self._lock:
            self._subscriptions.append(_Subscription(token=token, handler=handler))
        return token

    def unsubscribe(self, token: SubscriptionToken) -> bool:
        """
        Remove the subscription for token.

        Returns True if removed, False if already gone (idempotent).
        """
        with self._lock:
            before = len(self._subscriptions)
            self._subscriptions = [
                s for s in self._subscriptions if s.token.id != token.id
            ]
            removed = len(self._subscriptions) < before
        if removed:
            token._cancelled = True
        return removed

    def publish(self, event: str, data: Any = None) -> int:
        """
        Fire event to all matching subscribers.

        - Handlers run in subscription order.
        - All handlers run even if one raises; errors are collected and
          re-raised together as PublishError after dispatch completes.

        Returns:
            Number of handlers called.
        """
        with self._lock:
            # Snapshot inside lock; run handlers outside to avoid blocking
            targets = [
                s for s in self._subscriptions
                if fnmatch.fnmatch(event, s.token.pattern)
            ]

        errors: list[tuple[_Subscription, Exception]] = []
        for sub in targets:
            try:
                sub.handler(event, data)
            except Exception as exc:
                errors.append((sub, exc))

        if errors:
            raise PublishError(event, errors)

        return len(targets)

    def subscribers(self, event: str | None = None) -> list[SubscriptionToken]:
        """List active tokens, optionally filtered to those matching event."""
        with self._lock:
            subs = list(self._subscriptions)
        if event is None:
            return [s.token for s in subs]
        return [s.token for s in subs if fnmatch.fnmatch(event, s.token.pattern)]

    def clear(self) -> None:
        """Remove all subscriptions (great for test teardown)."""
        with self._lock:
            for sub in self._subscriptions:
                sub.token._cancelled = True
            self._subscriptions.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._subscriptions)

    def __repr__(self) -> str:
        return f"EventBus(subscriptions={len(self)})"


# ── Custom exception ──────────────────────────────────────────────────────────

class PublishError(Exception):
    """
    Raised when handlers throw during publish().
    All handlers still run first — no events are dropped.
    """
    def __init__(self, event: str, failures: list[tuple[_Subscription, Exception]]) -> None:
        self.event = event
        self.failures = failures
        msgs = "\n  ".join(
            f"[pattern={s.token.pattern}] {type(e).__name__}: {e}"
            for s, e in failures
        )
        super().__init__(f"{len(failures)} handler(s) failed for '{event}':\n  {msgs}")

bus = EventBus()
log = []

# 1. Exact match
t_login = bus.subscribe("user.login",  lambda e, d: log.append(f"LOGIN  → {d}"))

# 2. Wildcard: any user.X event
t_user  = bus.subscribe("user.*",      lambda e, d: log.append(f"USER   → {e}"))

# 3. Catch-all wildcard
t_all   = bus.subscribe("**",          lambda e, d: log.append(f"ALL    → {e}"))

# Publish user.login — hits all 3
bus.publish("user.login", {"user_id": 1, "ip": "192.168.1.1"})
# → LOGIN  → {'user_id': 1, 'ip': '192.168.1.1'}
# → USER   → user.login
# → ALL    → user.login

# Publish user.logout — hits user.* and **
bus.publish("user.logout", {"user_id": 1})
# → USER   → user.logout
# → ALL    → user.logout

# Unsubscribe the wildcard
t_user.cancel()
print(t_user.active)   # False

# Now user.login only hits t_login and t_all
bus.publish("user.login", {"user_id": 2})
# → LOGIN  → {'user_id': 2}
# → ALL    → user.login

# order.created — only ** matches
bus.publish("order.created", {"order_id": 99})
# → ALL    → order.created

print(len(bus))  # 2 (t_login + t_all still active)