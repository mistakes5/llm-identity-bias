"""
pubsub.py — Thread-safe publish-subscribe event bus with wildcard topics.

Topic syntax
────────────
  user.login          exact match
  user.*              one segment wildcard   (user.login ✓, user.profile.update ✗)
  user.**             multi-segment wildcard (user.login ✓, user.profile.update ✓)
  **                  matches every topic
"""
from __future__ import annotations

import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Optional

Handler = Callable[[str, Any], None]


@dataclass
class Subscription:
    """Opaque handle for a single registered handler."""
    id: str
    pattern: str
    handler: Handler
    once: bool = False


class EventBus:
    def __init__(self) -> None:
        self._subs: dict[str, list[Subscription]] = defaultdict(list)
        self._lock = threading.RLock()          # re-entrant: handlers may re-publish

    # ── Subscribe ─────────────────────────────────────────────────────────────

    def subscribe(self, pattern: str, handler: Handler, *, once: bool = False) -> str:
        """Register handler. Returns a subscription ID for later unsubscription."""
        sub = Subscription(id=str(uuid.uuid4()), pattern=pattern,
                           handler=handler, once=once)
        with self._lock:
            self._subs[pattern].append(sub)
        return sub.id

    def once(self, pattern: str, handler: Handler) -> str:
        """Subscribe for exactly one delivery, then auto-remove."""
        return self.subscribe(pattern, handler, once=True)

    def on(self, pattern: str) -> Callable[[Handler], Handler]:
        """Decorator: @bus.on('order.*')"""
        def decorator(fn: Handler) -> Handler:
            self.subscribe(pattern, fn)
            return fn
        return decorator

    # ── Unsubscribe ───────────────────────────────────────────────────────────

    def unsubscribe(self, subscription_id: str) -> bool:
        """Remove by ID. Returns True if found."""
        with self._lock:
            for subs in self._subs.values():
                for i, sub in enumerate(subs):
                    if sub.id == subscription_id:
                        subs.pop(i)
                        return True
        return False

    def clear(self, pattern: Optional[str] = None) -> None:
        """Remove all subscriptions, or only those for a specific pattern."""
        with self._lock:
            if pattern is None:
                self._subs.clear()
            else:
                self._subs.pop(pattern, None)

    # ── Publish ───────────────────────────────────────────────────────────────

    def publish(self, topic: str, data: Any = None) -> int:
        """
        Fire all matching handlers. Errors are isolated per-handler.
        Returns the number of handlers called.
        """
        matched: list[Subscription] = []

        with self._lock:
            for pattern, subs in self._subs.items():
                if self._matches(pattern, topic):
                    matched.extend(subs)
            for sub in matched:
                if sub.once:
                    try:
                        self._subs[sub.pattern].remove(sub)
                    except ValueError:
                        pass  # concurrent publish already removed it

        called = 0
        for sub in matched:
            try:
                sub.handler(topic, data)
                called += 1
            except Exception as exc:
                self._on_error(sub, exc)
        return called

    # ── Introspection ─────────────────────────────────────────────────────────

    def listener_count(self, topic: str) -> int:
        """How many handlers would fire for this topic right now?"""
        with self._lock:
            return sum(
                len(subs) for pat, subs in self._subs.items()
                if self._matches(pat, topic)
            )

    # ── Internals ─────────────────────────────────────────────────────────────

    def _on_error(self, sub: Subscription, exc: Exception) -> None:
        """Override to route errors to your logger."""
        print(f"[EventBus] Handler error in '{sub.pattern}': {exc!r}")

    def _matches(self, pattern: str, topic: str) -> bool:
        if pattern == topic:   return True   # fast path: exact
        if pattern == "**":    return True   # fast path: universal
        return self._match_parts(pattern.split("."), topic.split("."))

    def _match_parts(self, pattern: list[str], topic: list[str]) -> bool:
        """
        Recursively match segment lists with wildcard support.

        Rules:
          • literal  → must equal the topic segment exactly
          • '*'      → matches exactly ONE topic segment
          • '**'     → matches ZERO OR MORE topic segments

        ✏️ TODO — implement this (~10 lines).

        Base cases to reason about:
          1. Both empty                → True  (pattern fully consumed)
          2. Pattern empty, topic not  → False (leftover topic segments)
          3. Topic empty, pattern not  → True ONLY if all remaining
                                         pattern tokens are '**'
          4. Head is '**'              → try consuming 0, 1, 2… topic segments
          5. Head is '*' or literal    → consume exactly one segment each
        """
        raise NotImplementedError("Implement _match_parts — see the TODO above!")

"""example.py — demonstrates every feature of EventBus."""
from pubsub import EventBus

bus = EventBus()
log: list[str] = []

# ── 1. Decorator-style subscription ──────────────────────────────────────────
@bus.on("order.placed")
def on_order_placed(topic, data):
    log.append(f"placed: {data['id']}")

# ── 2. Wildcard: single segment ───────────────────────────────────────────────
order_id = bus.subscribe("order.*", lambda t, d: log.append(f"order.*: {t}"))

# ── 3. Wildcard: multi-segment ────────────────────────────────────────────────
bus.subscribe("order.**", lambda t, d: log.append(f"order.**: {t}"))

# ── 4. Universal wildcard ─────────────────────────────────────────────────────
bus.subscribe("**", lambda t, d: log.append(f"**: {t}"))

# ── 5. one-time subscription ──────────────────────────────────────────────────
bus.once("user.login", lambda t, d: log.append("first login only"))

# ── Publish and inspect ───────────────────────────────────────────────────────
print("=== Publish: order.placed ===")
bus.publish("order.placed", {"id": 99})
print("\n".join(f"  {x}" for x in log)); log.clear()

print("\n=== Publish: order.item.added (deep) ===")
bus.publish("order.item.added", {})
print("\n".join(f"  {x}" for x in log)); log.clear()

print("\n=== Publish: user.login (once) ===")
bus.publish("user.login", {"user": "alice"})
print("\n".join(f"  {x}" for x in log)); log.clear()

print("\n=== Publish: user.login (second time — once handler is gone) ===")
bus.publish("user.login", {"user": "bob"})
print("\n".join(f"  {x}" for x in log) or "  (no handlers)"); log.clear()

# ── Unsubscribe ───────────────────────────────────────────────────────────────
print(f"\n=== listener_count('order.placed') before unsub: {bus.listener_count('order.placed')}")
bus.unsubscribe(order_id)
print(f"=== listener_count('order.placed') after  unsub: {bus.listener_count('order.placed')}")

# ── Error isolation ───────────────────────────────────────────────────────────
print("\n=== Error isolation: bad handler should not block good handler ===")
bus.subscribe("crash.*", lambda t, d: (_ for _ in ()).throw(RuntimeError("boom")))
bus.subscribe("crash.*", lambda t, d: log.append("safe handler still ran"))
bus.publish("crash.test")
print("\n".join(f"  {x}" for x in log)); log.clear()

def _match_parts(self, pattern: list[str], topic: list[str]) -> bool:
    # Your ~10 lines go here
    ...