"""
Publish-subscribe event bus with wildcard subscriptions.

Wildcard patterns (segment separator is '.'):
  - '*'   matches exactly one segment   user.*  → user.created, user.deleted
  - '**'  matches zero or more segments app.**  → app.user.login, app.db.query.slow
"""
from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

Callback = Callable[[str, Any], None]


@dataclass(frozen=True)
class Subscription:
    id: str
    pattern: str
    callback: Callback


@dataclass
class PublishResult:
    event: str
    data: Any
    notified: int
    errors: list[tuple[Subscription, Exception]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


class EventBus:
    """Thread-safe publish-subscribe event bus."""

    def __init__(self) -> None:
        self._subscriptions: dict[str, Subscription] = {}
        self._lock = threading.RLock()

    def subscribe(self, pattern: str, callback: Callback) -> str:
        if not callable(callback):
            raise TypeError(f"callback must be callable, got {type(callback).__name__!r}")
        if not pattern:
            raise ValueError("pattern must not be empty")

        sub_id = str(uuid.uuid4())
        with self._lock:
            self._subscriptions[sub_id] = Subscription(sub_id, pattern, callback)
        return sub_id

    def unsubscribe(self, subscription_id: str) -> bool:
        with self._lock:
            return self._subscriptions.pop(subscription_id, None) is not None

    def publish(self, event: str, data: Any = None) -> PublishResult:
        if not event:
            raise ValueError("event name must not be empty")

        with self._lock:
            snapshot = list(self._subscriptions.values())

        result = PublishResult(event=event, data=data, notified=0)
        for sub in snapshot:
            if self._matches(sub.pattern, event):
                try:
                    sub.callback(event, data)
                    result.notified += 1
                except Exception as exc:
                    result.errors.append((sub, exc))
        return result

    def subscriber_count(self, pattern: str | None = None) -> int:
        with self._lock:
            if pattern is None:
                return len(self._subscriptions)
            return sum(1 for s in self._subscriptions.values() if s.pattern == pattern)

    def clear(self) -> int:
        with self._lock:
            count = len(self._subscriptions)
            self._subscriptions.clear()
            return count

    def _matches(self, pattern: str, event: str) -> bool:
        return _segment_match(pattern.split("."), event.split("."))


def _segment_match(pattern_parts: list[str], event_parts: list[str]) -> bool:
    p_idx = e_idx = 0
    p_len, e_len = len(pattern_parts), len(event_parts)

    while p_idx < p_len and e_idx < e_len:
        seg = pattern_parts[p_idx]
        if seg == "**":
            remaining = pattern_parts[p_idx + 1:]
            for consumed in range(e_len - e_idx + 1):
                if _segment_match(remaining, event_parts[e_idx + consumed:]):
                    return True
            return False
        if seg != "*" and seg != event_parts[e_idx]:
            return False
        p_idx += 1
        e_idx += 1

    while p_idx < p_len and pattern_parts[p_idx] == "**":
        p_idx += 1

    return p_idx == p_len and e_idx == e_len

from pubsub import EventBus

bus = EventBus()
log = []

# 1. Exact subscription
id1 = bus.subscribe("user.created", lambda e, d: log.append(("exact", d["name"])))

# 2. Single-segment wildcard
id2 = bus.subscribe("user.*", lambda e, d: log.append(("user.*", e)))

# 3. Deep wildcard
id3 = bus.subscribe("**", lambda e, d: log.append(("**", e)))

bus.publish("user.created", {"name": "Alice"})
print(log)
# [('exact', 'Alice'), ('user.*', 'user.created'), ('**', 'user.created')]

# 4. Only '**' matches a 3-level event
log.clear()
bus.publish("app.db.query", {"ms": 142})
assert any(tag == "**" for tag, _ in log)
assert not any(tag == "user.*" for tag, _ in log)

# 5. Unsubscribe
bus.unsubscribe(id3)
log.clear()
bus.publish("order.placed", {"total": 99})
assert all(tag != "**" for tag, _ in log)  # id3 removed

print("All assertions passed ✓")

import fnmatch

def _matches(self, pattern: str, event: str) -> bool:
    return fnmatch.fnmatch(event, pattern)
    # ⚠️ caveat: 'user.*' now matches 'user.profile.updated'
    #    '**' is not supported natively — use '*' for any depth

import re

def _matches(self, pattern: str, event: str) -> bool:
    # Convert glob-style to regex: ** → .*, * → [^.]*
    regex = re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", r"[^.]*")
    return bool(re.fullmatch(regex, event))