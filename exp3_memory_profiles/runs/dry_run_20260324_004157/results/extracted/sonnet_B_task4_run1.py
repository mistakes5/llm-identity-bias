# pubsub.py
"""
Publish-Subscribe Event Bus
============================
Thread-safe event bus with wildcard support (fnmatch-style patterns).

Wildcard syntax (fnmatch):
    'user.created'   — exact match
    'user.*'         — matches any single-segment suffix
    '*.created'      — matches any event ending in .created
    '*'              — matches every event
    'order.?.done'   — '?' matches exactly one character
"""

from __future__ import annotations

import fnmatch
import logging
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable

log = logging.getLogger(__name__)

Handler = Callable[[str, Any], None]


@dataclass
class Subscription:
    id: str
    pattern: str
    handler: Handler
    once: bool = False          # auto-remove after first invocation


class AggregateError(Exception):
    """Raised when error_strategy='collect' and one or more handlers fail."""

    def __init__(self, errors: list[tuple[str, Exception]]) -> None:
        self.errors = errors
        lines = [f"  [{sid[:8]}…] {type(e).__name__}: {e}" for sid, e in errors]
        super().__init__(f"{len(errors)} handler(s) raised:\n" + "\n".join(lines))


ErrorStrategy = Callable[[str, Subscription, Exception], None]


def _strategy_raise(event: str, sub: Subscription, exc: Exception) -> None:
    raise exc                   # stops all subsequent handlers


def _strategy_log(event: str, sub: Subscription, exc: Exception) -> None:
    log.error("[%s…] %r — %s: %s", sub.id[:8], event, type(exc).__name__, exc)


class EventBus:
    """
    Thread-safe publish-subscribe event bus.

    Args:
        error_strategy:
            'raise'   — re-raise the first exception (stops other handlers).
            'collect' — run ALL handlers, then raise AggregateError.
            'log'     — log each error, continue silently.
            Callable  — custom (event, subscription, exc) -> None function.
    """

    _STRATEGIES: dict[str, ErrorStrategy] = {
        "raise": _strategy_raise,
        "log": _strategy_log,
    }

    def __init__(self, error_strategy: str | ErrorStrategy = "raise") -> None:
        if callable(error_strategy):
            self._on_error: ErrorStrategy = error_strategy
            self._collect_mode = False
        elif error_strategy == "collect":
            self._on_error = _strategy_log       # unused in collect mode
            self._collect_mode = True
        else:
            try:
                self._on_error = self._STRATEGIES[error_strategy]
            except KeyError:
                raise ValueError(
                    f"Unknown error_strategy {error_strategy!r}. "
                    f"Choose from: {list(self._STRATEGIES)} or 'collect'."
                )
            self._collect_mode = False

        self._lock = threading.RLock()
        self._subscriptions: dict[str, Subscription] = {}
        self._exact_index: dict[str, list[str]] = defaultdict(list)  # O(1) hot path
        self._wildcard_ids: list[str] = []                           # scanned per-publish

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def subscribe(self, pattern: str, handler: Handler, *, once: bool = False) -> str:
        """
        Register *handler* for events matching *pattern*.
        Returns a token you can pass to unsubscribe().
        """
        token = str(uuid.uuid4())
        sub = Subscription(id=token, pattern=pattern, handler=handler, once=once)
        with self._lock:
            self._subscriptions[token] = sub
            if _is_wildcard(pattern):
                self._wildcard_ids.append(token)
            else:
                self._exact_index[pattern].append(token)
        return token

    def once(self, pattern: str, handler: Handler) -> str:
        """Subscribe; auto-unsubscribe after the first matching event."""
        return self.subscribe(pattern, handler, once=True)

    def unsubscribe(self, token: str) -> bool:
        """Remove a subscription. Returns True if the token was found."""
        with self._lock:
            return self._remove_locked(token)

    def publish(self, event: str, data: Any = None) -> int:
        """
        Emit *event* with an optional payload.
        Returns the number of handlers that were invoked.
        """
        with self._lock:
            # --- phase 1: collect matching tokens (under lock) ---
            matching: list[str] = list(self._exact_index.get(event, []))
            for wid in self._wildcard_ids:
                sub = self._subscriptions.get(wid)
                if sub and fnmatch.fnmatch(event, sub.pattern):
                    matching.append(wid)

            handlers: list[Subscription] = []
            to_remove: list[str] = []
            for sid in matching:
                sub = self._subscriptions.get(sid)
                if sub:
                    handlers.append(sub)
                    if sub.once:
                        to_remove.append(sid)
            for sid in to_remove:
                self._remove_locked(sid)

        # --- phase 2: dispatch (outside lock — handlers may re-publish) ---
        self._dispatch(event, data, handlers)
        return len(handlers)

    def clear(self, pattern: str | None = None) -> int:
        """Remove all subscriptions, or only those with a specific pattern."""
        with self._lock:
            if pattern is None:
                count = len(self._subscriptions)
                self._subscriptions.clear()
                self._exact_index.clear()
                self._wildcard_ids.clear()
                return count
            targets = [sid for sid, s in self._subscriptions.items()
                       if s.pattern == pattern]
            for sid in targets:
                self._remove_locked(sid)
            return len(targets)

    @property
    def subscription_count(self) -> int:
        with self._lock:
            return len(self._subscriptions)

    # ------------------------------------------------------------------ #
    #  Private helpers                                                     #
    # ------------------------------------------------------------------ #

    def _remove_locked(self, token: str) -> bool:
        sub = self._subscriptions.pop(token, None)
        if sub is None:
            return False
        if _is_wildcard(sub.pattern):
            try:
                self._wildcard_ids.remove(token)
            except ValueError:
                pass
        else:
            ids = self._exact_index.get(sub.pattern)
            if ids and token in ids:
                ids.remove(token)
        return True

    def _dispatch(self, event: str, data: Any, handlers: list[Subscription]) -> None:
        if self._collect_mode:
            errors: list[tuple[str, Exception]] = []
            for sub in handlers:
                try:
                    sub.handler(event, data)
                except Exception as exc:
                    errors.append((sub.id, exc))
            if errors:
                raise AggregateError(errors)
        else:
            for sub in handlers:
                try:
                    sub.handler(event, data)
                except Exception as exc:
                    self._on_error(event, sub, exc)


def _is_wildcard(pattern: str) -> bool:
    return any(c in pattern for c in ("*", "?", "["))

# test_pubsub.py
import pytest
from pubsub import AggregateError, EventBus


# ── Basic subscribe / publish ──────────────────────────────────────────────

def test_exact_match():
    bus = EventBus()
    received = []
    bus.subscribe("user.created", lambda e, d: received.append(d))
    bus.publish("user.created", {"id": 1})
    assert received == [{"id": 1}]


def test_no_match():
    bus = EventBus()
    received = []
    bus.subscribe("user.created", lambda e, d: received.append(d))
    bus.publish("order.created", {"id": 99})
    assert received == []


def test_publish_returns_handler_count():
    bus = EventBus()
    bus.subscribe("ping", lambda e, d: None)
    bus.subscribe("ping", lambda e, d: None)
    assert bus.publish("ping") == 2


# ── Unsubscribe ─────────────────────────────────────────────────────────────

def test_unsubscribe_stops_delivery():
    bus = EventBus()
    received = []
    token = bus.subscribe("tick", lambda e, d: received.append(d))
    bus.publish("tick", 1)
    bus.unsubscribe(token)
    bus.publish("tick", 2)
    assert received == [1]


def test_unsubscribe_unknown_token():
    bus = EventBus()
    assert bus.unsubscribe("nonexistent") is False


def test_subscription_count():
    bus = EventBus()
    t1 = bus.subscribe("a", lambda e, d: None)
    t2 = bus.subscribe("b.*", lambda e, d: None)
    assert bus.subscription_count == 2
    bus.unsubscribe(t1)
    assert bus.subscription_count == 1
    bus.unsubscribe(t2)
    assert bus.subscription_count == 0


# ── Wildcard subscriptions ───────────────────────────────────────────────────

def test_wildcard_star():
    bus = EventBus()
    received = []
    bus.subscribe("user.*", lambda e, d: received.append(e))
    bus.publish("user.created")
    bus.publish("user.deleted")
    bus.publish("order.created")      # should NOT match
    assert received == ["user.created", "user.deleted"]


def test_wildcard_global_star():
    bus = EventBus()
    received = []
    bus.subscribe("*", lambda e, d: received.append(e))
    bus.publish("anything")
    bus.publish("goes")
    assert received == ["anything", "goes"]


def test_wildcard_question_mark():
    bus = EventBus()
    received = []
    bus.subscribe("v?.deployed", lambda e, d: received.append(e))
    bus.publish("v1.deployed")
    bus.publish("v2.deployed")
    bus.publish("v10.deployed")   # two chars — should NOT match
    assert received == ["v1.deployed", "v2.deployed"]


def test_wildcard_prefix_star():
    bus = EventBus()
    received = []
    bus.subscribe("*.failed", lambda e, d: received.append(e))
    bus.publish("job.failed")
    bus.publish("deploy.failed")
    bus.publish("deploy.succeeded")  # should NOT match
    assert received == ["job.failed", "deploy.failed"]


def test_exact_and_wildcard_both_fire():
    bus = EventBus()
    log = []
    bus.subscribe("data.saved", lambda e, d: log.append("exact"))
    bus.subscribe("data.*",     lambda e, d: log.append("wildcard"))
    bus.publish("data.saved")
    assert log == ["exact", "wildcard"]


# ── once() / one-shot subscriptions ─────────────────────────────────────────

def test_once_fires_exactly_once():
    bus = EventBus()
    received = []
    bus.once("ping", lambda e, d: received.append(d))
    bus.publish("ping", 1)
    bus.publish("ping", 2)
    bus.publish("ping", 3)
    assert received == [1]
    assert bus.subscription_count == 0


def test_once_wildcard():
    bus = EventBus()
    received = []
    bus.once("order.*", lambda e, d: received.append(e))
    bus.publish("order.placed")
    bus.publish("order.shipped")   # already unsubscribed
    assert received == ["order.placed"]


# ── Error strategies ─────────────────────────────────────────────────────────

def test_error_strategy_raise():
    bus = EventBus(error_strategy="raise")
    bus.subscribe("boom", lambda e, d: (_ for _ in ()).throw(ValueError("oops")))
    with pytest.raises(ValueError, match="oops"):
        bus.publish("boom")


def test_error_strategy_log(caplog):
    bus = EventBus(error_strategy="log")
    bus.subscribe("boom", lambda e, d: (_ for _ in ()).throw(RuntimeError("kaboom")))
    with caplog.at_level(logging.ERROR):
        count = bus.publish("boom")
    assert count == 1
    assert "kaboom" in caplog.text


def test_error_strategy_collect_runs_all_handlers():
    bus = EventBus(error_strategy="collect")
    log = []
    bus.subscribe("e", lambda ev, d: log.append("first"))
    bus.subscribe("e", lambda ev, d: (_ for _ in ()).throw(ValueError("bad")))
    bus.subscribe("e", lambda ev, d: log.append("third"))
    with pytest.raises(AggregateError) as exc_info:
        bus.publish("e")
    assert log == ["first", "third"]   # third handler ran despite second failing
    assert len(exc_info.value.errors) == 1


def test_error_strategy_custom():
    caught = []
    def my_strategy(event, sub, exc):
        caught.append((event, str(exc)))
    bus = EventBus(error_strategy=my_strategy)
    bus.subscribe("x", lambda e, d: (_ for _ in ()).throw(TypeError("nope")))
    bus.publish("x")
    assert caught == [("x", "nope")]


# ── Thread safety ─────────────────────────────────────────────────────────────

def test_concurrent_publish_subscribe():
    bus = EventBus()
    results = []
    lock = threading.Lock()

    def listener(e, d):
        with lock:
            results.append(d)

    tokens = [bus.subscribe("tick", listener) for _ in range(5)]

    threads = [threading.Thread(target=bus.publish, args=("tick", i)) for i in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 100   # 20 publishes × 5 subscribers


# ── clear() ───────────────────────────────────────────────────────────────────

def test_clear_all():
    bus = EventBus()
    bus.subscribe("a", lambda e, d: None)
    bus.subscribe("b.*", lambda e, d: None)
    removed = bus.clear()
    assert removed == 2
    assert bus.subscription_count == 0


def test_clear_by_pattern():
    bus = EventBus()
    bus.subscribe("a", lambda e, d: None)
    bus.subscribe("a", lambda e, d: None)
    bus.subscribe("b", lambda e, d: None)
    removed = bus.clear("a")
    assert removed == 2
    assert bus.subscription_count == 1


# ── Re-entrant publish (handler calls publish) ────────────────────────────────

def test_handler_can_republish():
    bus = EventBus()
    log = []

    def on_ping(e, d):
        log.append("ping")
        if d < 3:
            bus.publish("ping", d + 1)   # re-entrant publish

    bus.subscribe("ping", on_ping)
    bus.publish("ping", 1)
    assert log == ["ping", "ping", "ping"]

# Add to EventBus.__init__:
self._middleware: list[Callable[[str, Any], Any]] = []

def use(self, fn: Callable[[str, Any], Any]) -> None:
    """Register a middleware function called before every dispatch."""
    self._middleware.append(fn)