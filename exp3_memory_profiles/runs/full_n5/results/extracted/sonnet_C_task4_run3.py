"""
Publish-Subscribe Event Bus
===========================
Supports:
  - Exact match:           "user.created"
  - Single-level wildcard: "user.*"   → matches "user.created" but NOT "user.created.v2"
  - Multi-level wildcard:  "user.**"  → matches "user.created" AND "user.created.v2"
  - Global wildcard:       "*"        → matches every topic
"""

from __future__ import annotations
import threading
import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Subscription:
    """Opaque handle returned by subscribe(). Pass to unsubscribe() to cancel."""
    id: str
    topic: str
    handler: Callable[[str, Any], None]


class EventBus:
    """Thread-safe publish-subscribe event bus with wildcard topic support."""

    def __init__(self) -> None:
        self._subscriptions: dict[str, list[Subscription]] = defaultdict(list)
        self._lock = threading.Lock()

    def subscribe(self, topic: str, handler: Callable[[str, Any], None]) -> Subscription:
        """Subscribe to a topic pattern. Returns a handle for unsubscribing."""
        sub = Subscription(id=str(uuid.uuid4()), topic=topic, handler=handler)
        with self._lock:
            self._subscriptions[topic].append(sub)
        return sub

    def unsubscribe(self, subscription: Subscription) -> bool:
        """Cancel a subscription. Returns True if found and removed."""
        with self._lock:
            subs = self._subscriptions.get(subscription.topic, [])
            updated = [s for s in subs if s.id != subscription.id]
            removed = len(updated) < len(subs)
            self._subscriptions[subscription.topic] = updated
        return removed

    def publish(self, topic: str, data: Any = None) -> int:
        """Publish an event. Returns the number of handlers invoked."""
        # Snapshot handlers OUTSIDE the lock to avoid deadlocks
        # if a handler tries to subscribe/publish.
        matched: list[Subscription] = []
        with self._lock:
            for pattern, subs in self._subscriptions.items():
                if self._match_pattern(pattern, topic):
                    matched.extend(subs)

        for sub in matched:
            sub.handler(topic, data)
        return len(matched)

    def clear(self, topic: str | None = None) -> None:
        """Remove all subscriptions, or only those for a specific pattern."""
        with self._lock:
            if topic is None:
                self._subscriptions.clear()
            else:
                self._subscriptions.pop(topic, None)

    @property
    def subscription_count(self) -> int:
        with self._lock:
            return sum(len(subs) for subs in self._subscriptions.values())

    # ---------------------------------------------------------------
    # TODO — your turn!
    # ---------------------------------------------------------------
    def _match_pattern(self, pattern: str, topic: str) -> bool:
        """
        Return True if *topic* matches *pattern*.

        Rules:
          pattern == topic  → exact match, always True
          pattern == "*"    → global wildcard, matches everything
          "order.*"         → matches "order.created", NOT "order.created.v2"
          "order.**"        → matches "order.created" AND "order.created.v2"

        Hint: split both strings on "." and walk the segments.
        About 8–12 lines is plenty.
        """
        # ✏️  Implement here
        raise NotImplementedError