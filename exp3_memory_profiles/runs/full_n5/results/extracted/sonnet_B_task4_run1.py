"""
pubsub.py — Thread-safe publish-subscribe event bus with wildcard support.

Wildcard patterns use fnmatch syntax:
  '*'     matches any sequence of characters
  '?'     matches any single character
  '[seq]' matches any character in seq

Examples:
  subscribe('user.*', cb)     → 'user.login', 'user.logout', 'user.signup'
  subscribe('*.created', cb)  → 'order.created', 'post.created'
  subscribe('*', cb)          → every event published
"""

import fnmatch
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


# ── Subscription token ───────────────────────────────────────────────────────

@dataclass
class Subscription:
    """
    Returned by EventBus.subscribe(). Holds a cancellable reference.

    Usage:
        sub = bus.subscribe('user.*', handler)
        sub.cancel()                      # explicit unsubscribe

        with bus.subscribe('tick', handler):
            ...                           # auto-unsubscribes on exit
    """
    id: str
    pattern: str
    callback: Callable
    _bus: "EventBus" = field(repr=False)

    def cancel(self) -> bool:
        """Cancel this subscription. Returns True if it was still active."""
        return self._bus.unsubscribe(self.id)

    def __enter__(self) -> "Subscription":
        return self

    def __exit__(self, *_) -> None:
        self.cancel()


# ── EventBus ─────────────────────────────────────────────────────────────────

class EventBus:
    """
    Thread-safe publish-subscribe event bus.

    Args:
        error_handler: Optional callable(exc, callback, event, data) invoked
                       when a subscriber raises. Controls error behaviour;
                       see _handle_callback_error() for strategy options.
    """

    def __init__(self, error_handler: Optional[Callable] = None) -> None:
        # { pattern: { subscription_id: Subscription } }
        self._subscriptions: dict[str, dict[str, Subscription]] = defaultdict(dict)
        # RLock — reentrant so callbacks that publish/subscribe won't deadlock.
        self._lock = threading.RLock()
        self._error_handler = error_handler

    # ── Subscribe ─────────────────────────────────────────────────────────────

    def subscribe(self, pattern: str, callback: Callable) -> Subscription:
        """
        Subscribe *callback* to all events matching *pattern*.

        Args:
            pattern:  fnmatch pattern, e.g. 'user.*', '*.created', '*'.
            callback: Callable with signature (event: str, data: Any) -> None.

        Returns:
            Subscription token — call .cancel() or use as context manager.
        """
        sub = Subscription(id=str(uuid.uuid4()), pattern=pattern,
                           callback=callback, _bus=self)
        with self._lock:
            self._subscriptions[pattern][sub.id] = sub
        return sub

    def once(self, pattern: str, callback: Callable) -> Subscription:
        """
        Subscribe to the *first* event matching *pattern*, then auto-cancel.

        Args:
            pattern:  Same as subscribe().
            callback: Same as subscribe().

        Returns:
            Subscription token (will be cancelled after first match).
        """
        holder: list[Subscription] = []

        def _one_shot(event: str, data: Any) -> None:
            if holder:
                holder[0].cancel()       # cancel before calling → safe re-entry
            callback(event, data)

        sub = self.subscribe(pattern, _one_shot)
        holder.append(sub)
        return sub

    # ── Unsubscribe ───────────────────────────────────────────────────────────

    def unsubscribe(self, subscription_id: str) -> bool:
        """
        Remove a subscription by its ID.

        Returns:
            True if found and removed, False if already gone.
        """
        with self._lock:
            for pattern, subs in list(self._subscriptions.items()):
                if subscription_id in subs:
                    del subs[subscription_id]
                    if not subs:                 # prune empty patterns
                        del self._subscriptions[pattern]
                    return True
        return False

    # ── Publish ───────────────────────────────────────────────────────────────

    def publish(self, event: str, data: Any = None) -> int:
        """
        Publish *event* with optional *data* to all matching subscribers.

        Callbacks are snapshotted under the lock then called outside it,
        so subscribers can safely publish/subscribe without deadlocking.

        Returns:
            Number of callbacks that completed without raising.
        """
        callbacks: list[Callable] = []
        with self._lock:
            for pattern, subs in self._subscriptions.items():
                if fnmatch.fnmatch(event, pattern):
                    callbacks.extend(sub.callback for sub in subs.values())

        count = 0
        for cb in callbacks:
            try:
                cb(event, data)
                count += 1
            except Exception as exc:
                self._handle_callback_error(exc, cb, event, data)

        return count

    # ── Error handling — YOUR CONTRIBUTION ───────────────────────────────────

    def _handle_callback_error(
        self,
        exc: Exception,
        callback: Callable,
        event: str,
        data: Any,
    ) -> None:
        """
        Called when a subscriber raises during publish().

        TODO: implement your error-handling strategy here (5–10 lines).

        See the table below for trade-offs:

        ┌──────────────────────────────┬──────────────────────────────────────────────┐
        │ Strategy                     │ Effect                                       │
        ├──────────────────────────────┼──────────────────────────────────────────────┤
        │ pass (silent ignore)         │ Resilient — other callbacks always fire,     │
        │                              │ but errors are invisible                     │
        ├──────────────────────────────┼──────────────────────────────────────────────┤
        │ raise exc                    │ Strict — fails fast, stops remaining cbs     │
        ├──────────────────────────────┼──────────────────────────────────────────────┤
        │ delegate → re-raise fallback │ Call self._error_handler if set, else raise  │
        │                              │ Most flexible — caller picks the policy      │
        ├──────────────────────────────┼──────────────────────────────────────────────┤
        │ log and continue             │ Visibility without disruption — good for     │
        │                              │ production systems                           │
        └──────────────────────────────┴──────────────────────────────────────────────┘

        Args:
            exc:      The exception that was raised.
            callback: The callback that raised it.
            event:    The event name that triggered publish().
            data:     The payload passed to publish().
        """
        # ── Your implementation here ──────────────────────────────────────
        pass

    # ── Utilities ─────────────────────────────────────────────────────────────

    def subscriber_count(self, pattern: Optional[str] = None) -> int:
        """Total active subscribers, or count for a specific *pattern*."""
        with self._lock:
            if pattern is not None:
                return len(self._subscriptions.get(pattern, {}))
            return sum(len(s) for s in self._subscriptions.values())

    def clear(self) -> None:
        """Remove all subscriptions."""
        with self._lock:
            self._subscriptions.clear()

    def __repr__(self) -> str:
        return (f"EventBus(patterns={len(self._subscriptions)}, "
                f"subscribers={self.subscriber_count()})")

import unittest
from pubsub import EventBus


class TestEventBus(unittest.TestCase):

    def setUp(self):
        self.bus = EventBus()

    # ── Basic subscribe / publish ─────────────────────────────────────────────

    def test_basic_publish(self):
        received = []
        self.bus.subscribe('order.created', lambda e, d: received.append(d))
        self.bus.publish('order.created', {'id': 42})
        self.assertEqual(received, [{'id': 42}])

    def test_publish_returns_invocation_count(self):
        self.bus.subscribe('ping', lambda e, d: None)
        self.bus.subscribe('ping', lambda e, d: None)
        self.assertEqual(self.bus.publish('ping'), 2)

    def test_publish_no_subscribers(self):
        self.assertEqual(self.bus.publish('ghost.event'), 0)

    def test_multiple_subscribers_all_notified(self):
        log = []
        self.bus.subscribe('tick', lambda e, d: log.append('a'))
        self.bus.subscribe('tick', lambda e, d: log.append('b'))
        self.bus.publish('tick')
        self.assertCountEqual(log, ['a', 'b'])

    def test_event_and_data_forwarded(self):
        received = []
        self.bus.subscribe('msg', lambda e, d: received.append((e, d)))
        self.bus.publish('msg', 'hello')
        self.assertEqual(received, [('msg', 'hello')])

    # ── Unsubscribe ───────────────────────────────────────────────────────────

    def test_unsubscribe_stops_delivery(self):
        log = []
        sub = self.bus.subscribe('click', lambda e, d: log.append(d))
        self.bus.publish('click', 1)
        sub.cancel()
        self.bus.publish('click', 2)
        self.assertEqual(log, [1])

    def test_unsubscribe_nonexistent_returns_false(self):
        self.assertFalse(self.bus.unsubscribe('not-a-real-id'))

    def test_context_manager_auto_unsubscribes(self):
        log = []
        with self.bus.subscribe('event', lambda e, d: log.append(d)):
            self.bus.publish('event', 'inside')
        self.bus.publish('event', 'outside')
        self.assertEqual(log, ['inside'])

    # ── Wildcard subscriptions ────────────────────────────────────────────────

    def test_wildcard_suffix(self):
        log = []
        self.bus.subscribe('user.*', lambda e, d: log.append(e))
        self.bus.publish('user.login')
        self.bus.publish('user.logout')
        self.bus.publish('order.created')       # must NOT match
        self.assertEqual(log, ['user.login', 'user.logout'])

    def test_wildcard_prefix(self):
        log = []
        self.bus.subscribe('*.created', lambda e, d: log.append(e))
        self.bus.publish('order.created')
        self.bus.publish('post.created')
        self.bus.publish('post.deleted')        # must NOT match
        self.assertEqual(log, ['order.created', 'post.created'])

    def test_wildcard_catch_all(self):
        log = []
        self.bus.subscribe('*', lambda e, d: log.append(e))
        self.bus.publish('anything')
        self.bus.publish('everything')
        self.assertCountEqual(log, ['anything', 'everything'])

    def test_exact_and_wildcard_both_fire(self):
        log = []
        self.bus.subscribe('user.login', lambda e, d: log.append('exact'))
        self.bus.subscribe('user.*',     lambda e, d: log.append('wildcard'))
        self.bus.publish('user.login')
        self.assertCountEqual(log, ['exact', 'wildcard'])

    # ── once() ───────────────────────────────────────────────────────────────

    def test_once_fires_only_once(self):
        log = []
        self.bus.once('signal', lambda e, d: log.append(d))
        self.bus.publish('signal', 1)
        self.bus.publish('signal', 2)
        self.assertEqual(log, [1])

    def test_once_wildcard(self):
        log = []
        self.bus.once('user.*', lambda e, d: log.append(e))
        self.bus.publish('user.login')
        self.bus.publish('user.logout')         # should NOT fire once() callback
        self.assertEqual(log, ['user.login'])

    # ── Thread safety ─────────────────────────────────────────────────────────

    def test_concurrent_publish(self):
        counter = []
        lock = threading.Lock()

        def cb(e, d):
            with lock:
                counter.append(1)

        for _ in range(10):
            self.bus.subscribe('concurrent', cb)

        threads = [
            threading.Thread(target=self.bus.publish, args=('concurrent',))
            for _ in range(20)
        ]
        for t in threads: t.start()
        for t in threads: t.join()

        self.assertEqual(len(counter), 200)     # 20 publishes × 10 subscribers

    def test_callback_can_subscribe_without_deadlock(self):
        """A callback that calls subscribe() must not deadlock (RLock check)."""
        inner_fired = []

        def outer(e, d):
            self.bus.subscribe('inner', lambda e2, d2: inner_fired.append(d2))

        self.bus.subscribe('outer', outer)
        self.bus.publish('outer')
        self.bus.publish('inner', 99)
        self.assertEqual(inner_fired, [99])

    # ── Utilities ─────────────────────────────────────────────────────────────

    def test_subscriber_count_total(self):
        self.bus.subscribe('a', lambda e, d: None)
        self.bus.subscribe('a', lambda e, d: None)
        self.bus.subscribe('b', lambda e, d: None)
        self.assertEqual(self.bus.subscriber_count(), 3)

    def test_subscriber_count_per_pattern(self):
        self.bus.subscribe('a', lambda e, d: None)
        self.bus.subscribe('a', lambda e, d: None)
        self.bus.subscribe('b', lambda e, d: None)
        self.assertEqual(self.bus.subscriber_count('a'), 2)
        self.assertEqual(self.bus.subscriber_count('b'), 1)

    def test_clear(self):
        self.bus.subscribe('x', lambda e, d: None)
        self.bus.clear()
        self.assertEqual(self.bus.subscriber_count(), 0)
        self.assertEqual(self.bus.publish('x'), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)

def _handle_callback_error(self, exc, callback, event, data):
    if self._error_handler is not None:
        self._error_handler(exc, callback, event, data)   # caller decides
    else:
        raise exc                                          # strict default

def _handle_callback_error(self, exc, callback, event, data):
    import logging
    logging.getLogger(__name__).error(
        "Subscriber %s raised on event %r: %s",
        callback.__qualname__, event, exc, exc_info=True
    )
    # returning normally → publish() continues to the next callback