"""
Publish-subscribe event bus with segment-aware wildcard routing.

Pattern syntax (dot-delimited):
    'order.created'  — exact
    'order.*'        — one segment   (order.created ✓, order.item.added ✗)
    'order.**'       — multi-segment (order.created ✓, order.item.added ✓)
    '**'             — global catch-all
"""
from __future__ import annotations

import fnmatch
import threading
import uuid
import weakref
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

Handler = Callable[[str, Any], None]


# ── Pattern matching ──────────────────────────────────────────────────────────

def _segment_match(pattern: str, event: str) -> bool:
    if pattern == "**":
        return True
    if "*" not in pattern and "?" not in pattern:
        return pattern == event
    return _match_parts(pattern.split("."), event.split("."))


def _match_parts(p: list[str], e: list[str]) -> bool:
    if not p and not e:
        return True
    if not p:
        return False
    if p[0] == "**":
        for i in range(len(e) + 1):
            if _match_parts(p[1:], e[i:]):
                return True
        return False
    if not e:
        return False
    head_ok = p[0] == "*" or fnmatch.fnmatch(e[0], p[0])
    return head_ok and _match_parts(p[1:], e[1:])


# ── Subscription token ────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Subscription:
    """Returned by subscribe(). Cancel via .cancel() or use as a context manager."""
    id: str
    pattern: str
    _bus: "EventBus" = field(repr=False, compare=False, hash=False)

    def cancel(self) -> bool:
        return self._bus.unsubscribe(self)

    def __enter__(self) -> "Subscription":
        return self

    def __exit__(self, *_: object) -> None:
        self.cancel()


# ── EventBus ──────────────────────────────────────────────────────────────────

class EventBus:
    """Thread-safe publish-subscribe bus with wildcard routing."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subs: dict[str, tuple[str, Any]] = {}          # id → (pattern, ref)
        self._by_pattern: dict[str, set[str]] = defaultdict(set)  # pattern → {ids}

    # ── Subscribe / unsubscribe ───────────────────────────────────────────────

    def subscribe(
        self,
        pattern: str,
        handler: Handler,
        *,
        weak: bool = False,
    ) -> Subscription:
        """
        Register handler for events matching pattern.

        weak=True holds only a weakref — subscription auto-removes when the
        handler is GC'd. Use for bound-method subscribers that must not
        extend object lifetime.
        """
        sub_id = uuid.uuid4().hex
        ref: Any

        if weak:
            if hasattr(handler, "__self__"):          # bound method
                ref = weakref.WeakMethod(handler)
            else:
                try:
                    ref = weakref.ref(handler)
                except TypeError:                     # lambdas / C extensions
                    ref = handler
        else:
            ref = handler

        with self._lock:
            self._subs[sub_id] = (pattern, ref)
            self._by_pattern[pattern].add(sub_id)

        return Subscription(id=sub_id, pattern=pattern, _bus=self)

    def unsubscribe(self, token: Subscription | str) -> bool:
        """Remove subscription. Returns True if it was active."""
        sub_id = token.id if isinstance(token, Subscription) else token
        with self._lock:
            entry = self._subs.pop(sub_id, None)
            if entry is None:
                return False
            pattern, _ = entry
            self._by_pattern[pattern].discard(sub_id)
            if not self._by_pattern[pattern]:
                del self._by_pattern[pattern]
        return True

    # ── Publish ───────────────────────────────────────────────────────────────

    def publish(self, event: str, data: Any = None) -> int:
        """
        Dispatch event to all matching subscribers synchronously.
        Dead weak-ref subscribers are pruned automatically.
        Returns count of handlers invoked.
        """
        handlers = list(self._resolve_handlers(event))
        for handler in handlers:
            self._dispatch(event, data, handler)
        return len(handlers)

    # ── Introspection ─────────────────────────────────────────────────────────

    def subscriber_count(self, event: str | None = None) -> int:
        with self._lock:
            if event is None:
                return len(self._subs)
            return sum(
                1 for _, (pat, _) in self._subs.items()
                if _segment_match(pat, event)
            )

    def patterns(self) -> list[str]:
        with self._lock:
            return list(self._by_pattern)

    def clear(self) -> None:
        with self._lock:
            self._subs.clear()
            self._by_pattern.clear()

    # ── Internals ─────────────────────────────────────────────────────────────

    def _resolve_handlers(self, event: str) -> Iterator[Handler]:
        dead: list[str] = []

        with self._lock:
            snapshot = list(self._subs.items())

        for sub_id, (pattern, ref) in snapshot:
            if not _segment_match(pattern, event):
                continue
            if isinstance(ref, weakref.ref):
                handler = ref()
                if handler is None:
                    dead.append(sub_id)
                    continue
            else:
                handler = ref
            yield handler

        if dead:
            with self._lock:
                for sid in dead:
                    self._prune(sid)

    def _prune(self, sub_id: str) -> None:
        entry = self._subs.pop(sub_id, None)
        if entry:
            pattern, _ = entry
            self._by_pattern[pattern].discard(sub_id)
            if not self._by_pattern[pattern]:
                del self._by_pattern[pattern]

    def _dispatch(self, event: str, data: Any, handler: Handler) -> None:
        """
        TODO — your error handling policy lives here.

        Three strategies with distinct ETL implications:

        A) Fail-fast — best for pipeline integrity:
               handler(event, data)
           Exceptions propagate; remaining handlers in this publish() are skipped.
           CAP equivalent: prefer consistency over availability.

        B) Resilient delivery — best for fanout / UI buses:
               try:
                   handler(event, data)
               except Exception:
                   logging.getLogger(__name__).exception(
                       "Handler %r failed on %r", handler, event)
           All subscribers always run. One bad handler can't take down others.

        C) Dead-letter — best for durable pipelines with retry:
               try:
                   handler(event, data)
               except Exception as exc:
                   self._dead_letter(event, data, handler, exc)
           Failed events are re-routable / retryable downstream.

        Constraints:
        - No lock is held when this runs — safe to call subscribe() inside a handler.
        - Raising here aborts remaining handlers in publish() unless you catch inside.
        - For async handlers: schedule onto an asyncio loop here instead of calling directly.
        """
        handler(event, data)

bus = EventBus()

# Exact subscription
bus.subscribe("order.created", lambda e, d: print(f"{e}: {d}"))

# Single-segment wildcard
bus.subscribe("order.*", lambda e, d: print(f"any order event: {e}"))

# Multi-segment wildcard — catches order.item.added, order.item.removed, etc.
bus.subscribe("order.**", lambda e, d: print(f"deep match: {e}"))

# Global audit log
bus.subscribe("**", lambda e, d: audit_log(e, d))

# Context-manager unsubscribe
with bus.subscribe("payment.failed", alert_team) as sub:
    process_batch()
# sub auto-cancelled here

# Token-based unsubscribe
token = bus.subscribe("etl.checkpoint", save_offset)
bus.publish("etl.checkpoint", {"offset": 12_500})
bus.unsubscribe(token)

# Weak-ref (instance method — won't prevent GC)
processor = StreamProcessor()
bus.subscribe("record.**", processor.handle, weak=True)

print(bus.subscriber_count("order.created"))  # → 3 (exact + two wildcards)