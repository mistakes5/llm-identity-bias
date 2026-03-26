"""
Publish-subscribe event bus with dot-segment wildcard patterns.

Pattern syntax:
  user.created   — exact match
  user.*         — one segment   (matches user.created, NOT user.profile.updated)
  user.**        — many segments (matches user.profile.updated)
  **             — match everything
"""
from __future__ import annotations

import asyncio
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Coroutine, Iterator

Handler = Callable[[str, Any], Any | Coroutine[Any, Any, Any]]
ErrorHandler = Callable[[Exception, "Subscription"], None]


@dataclass(frozen=True, slots=True)
class Subscription:
    id: int
    pattern: str
    handler: Handler


class DispatchError(Exception):
    """Aggregated handler failures from a single publish call."""
    def __init__(self, failures: list[tuple[Subscription, Exception]]) -> None:
        self.failures = failures
        detail = "; ".join(
            f"[sub={s.id} {s.pattern!r}] {type(e).__name__}: {e}"
            for s, e in failures
        )
        super().__init__(f"{len(failures)} handler(s) failed: {detail}")


class PatternMatcher:
    """Dot-segment-aware glob.  *=one segment  **=zero-or-more segments."""

    @classmethod
    def matches(cls, pattern: str, event: str) -> bool:
        return cls._match(pattern.split("."), event.split("."))

    @classmethod
    def _match(cls, pp: list[str], ep: list[str]) -> bool:
        if not pp and not ep:
            return True
        if not pp:
            return False
        head, tail = pp[0], pp[1:]
        if head == "**":
            return not tail or any(cls._match(tail, ep[i:]) for i in range(len(ep) + 1))
        if not ep:
            return False
        return (head == "*" or head == ep[0]) and cls._match(tail, ep[1:])


class EventBus:
    """Thread-safe pub-sub bus.

    Args:
        error_handler: If set, exceptions are isolated per-handler and routed
                       here instead of propagating. When None, _dispatch decides.
    """

    def __init__(self, error_handler: ErrorHandler | None = None) -> None:
        self._subs: list[Subscription] = []
        self._lock = threading.RLock()
        self._counter = 0
        self.error_handler = error_handler

    # ── Subscription management ───────────────────────────────────────────────

    def subscribe(self, pattern: str, handler: Handler) -> int:
        """Returns subscription ID for later unsubscribe."""
        with self._lock:
            self._counter += 1
            self._subs.append(Subscription(self._counter, pattern, handler))
            return self._counter

    def unsubscribe(self, subscription_id: int) -> bool:
        """Returns True if the subscription existed."""
        with self._lock:
            before = len(self._subs)
            self._subs = [s for s in self._subs if s.id != subscription_id]
            return len(self._subs) < before

    @contextmanager
    def subscription(self, pattern: str, handler: Handler) -> Iterator[int]:
        """Auto-unsubscribes on block exit — preferred for bounded lifetimes."""
        sub_id = self.subscribe(pattern, handler)
        try:
            yield sub_id
        finally:
            self.unsubscribe(sub_id)

    # ── Publishing ────────────────────────────────────────────────────────────

    def publish(self, event: str, data: Any = None) -> int:
        """Sync publish. Returns handler count."""
        return self._dispatch(event, data, self._snapshot(event))

    async def publish_async(self, event: str, data: Any = None) -> int:
        """Async publish. Async handlers gathered concurrently."""
        return await self._dispatch_async(event, data, self._snapshot(event))

    # ── Internals ─────────────────────────────────────────────────────────────

    def _snapshot(self, event: str) -> list[Subscription]:
        """Read matching subs under lock — dispatch runs outside to prevent deadlock
        when a handler re-publishes to this same bus."""
        with self._lock:
            return [s for s in self._subs if PatternMatcher.matches(s.pattern, event)]

    def _dispatch(self, event: str, data: Any, subs: list[Subscription]) -> int:
        """
        TODO — implement your error isolation strategy (5–10 lines).

        Three approaches — pick one based on your consistency requirements:

          1. Fail-fast   — re-raise on first exception; remaining handlers skipped.
                           Right for transactional flows where order matters.

          2. Best-effort — run ALL handlers, collect (sub, exc) pairs, raise
                           DispatchError at the end. Right for ETL fan-out where
                           every consumer must attempt regardless of siblings.

          3. Isolated    — per-handler try/except; route to self.error_handler
                           if set, silently swallow otherwise.
                           Right for observability hooks that must never interrupt flow.

        Return the count of handlers successfully invoked.
        """
        called = 0
        for sub in subs:
            result = sub.handler(event, data)
            if asyncio.iscoroutine(result):
                asyncio.run(result)   # sync callers get a new loop per coroutine
            called += 1
        return called

    async def _dispatch_async(
        self, event: str, data: Any, subs: list[Subscription]
    ) -> int:
        """Best-effort async dispatch: all handlers run, failures collected."""
        failures: list[tuple[Subscription, Exception]] = []
        coros: list[tuple[Subscription, Coroutine[Any, Any, Any]]] = []

        for sub in subs:
            try:
                result = sub.handler(event, data)
                if asyncio.iscoroutine(result):
                    coros.append((sub, result))
            except Exception as exc:
                (self.error_handler(exc, sub) if self.error_handler
                 else failures.append((sub, exc)))

        if coros:
            gathered = await asyncio.gather(
                *(c for _, c in coros), return_exceptions=True
            )
            for (sub, _), res in zip(coros, gathered):
                if isinstance(res, Exception):
                    (self.error_handler(res, sub) if self.error_handler
                     else failures.append((sub, res)))

        if failures:
            raise DispatchError(failures)
        return len(subs)

# test_event_bus.py
from event_bus import EventBus, DispatchError

bus = EventBus()
log: list[str] = []

# ── wildcard subscriptions ────────────────────────────────────────────────────
bus.subscribe("order.*",   lambda e, d: log.append(f"order-tier:{e}"))
bus.subscribe("order.**",  lambda e, d: log.append(f"deep:{e}"))
bus.subscribe("**",        lambda e, d: log.append(f"global:{e}"))

# ── exact + unsubscribe ───────────────────────────────────────────────────────
sid = bus.subscribe("order.placed", lambda e, d: log.append(f"exact:{d['id']}"))
bus.publish("order.placed", {"id": 42})
bus.unsubscribe(sid)
bus.publish("order.placed", {"id": 99})   # exact handler gone

# ── deep event (only ** matches, not *) ───────────────────────────────────────
bus.publish("order.line.added", {"sku": "X1"})

# ── context manager auto-cleanup ──────────────────────────────────────────────
with bus.subscription("user.created", lambda e, d: log.append("ctx:user")):
    bus.publish("user.created", {})
bus.publish("user.created", {})           # handler already removed

# ── async handlers ────────────────────────────────────────────────────────────
async def async_handler(event: str, data: Any) -> None:
    await asyncio.sleep(0)
    log.append(f"async:{event}")

bus.subscribe("metric.*", async_handler)

async def main():
    await bus.publish_async("metric.cpu", {"pct": 72.4})

asyncio.run(main())

print("\n".join(log))

def _dispatch(self, event: str, data: Any, subs: list[Subscription]) -> int:
    # YOUR IMPLEMENTATION HERE