from typing import Any, Callable, Dict, List, Pattern, Union
from dataclasses import dataclass, field
from threading import RLock
import re
import uuid
from enum import Enum


class MatchMode(Enum):
    EXACT = "exact"              # foo.bar matches foo.bar only
    PREFIX = "prefix"            # foo.* matches foo.bar, foo.baz
    REGEX = "regex"              # ^foo\..*\.error$ full regex


@dataclass
class Event:
    """Immutable event object."""
    topic: str
    data: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class EventBus:
    """Thread-safe pub-sub with wildcard support."""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._wildcard_subscribers: List[tuple[Pattern, Callable, MatchMode]] = []
        self._lock = RLock()
        self._error_handlers: List[Callable[[str, Event, Exception], None]] = []

    def subscribe(
        self,
        topic: str,
        callback: Callable[[Event], None],
        match_mode: MatchMode = MatchMode.EXACT,
    ):
        """Subscribe to topic with specified matching strategy."""
        with self._lock:
            if match_mode == MatchMode.EXACT:
                if topic not in self._subscribers:
                    self._subscribers[topic] = []
                self._subscribers[topic].append(callback)
            
            elif match_mode == MatchMode.PREFIX:
                # foo.* → ^foo\..*$
                pattern_str = topic.replace(".", r"\.").replace(r"\*", ".*")
                pattern = re.compile(f"^{pattern_str}$")
                self._wildcard_subscribers.append((pattern, callback, MatchMode.PREFIX))
            
            elif match_mode == MatchMode.REGEX:
                pattern = re.compile(topic)
                self._wildcard_subscribers.append((pattern, callback, MatchMode.REGEX))

    def publish(self, event: Event) -> int:
        """Publish event. Returns callback count invoked."""
        if not event.topic:
            raise ValueError("Event topic cannot be empty")

        # Snapshot callbacks under lock
        with self._lock:
            callbacks = self._subscribers.get(event.topic, []).copy()
            for pattern, callback, _ in self._wildcard_subscribers:
                if pattern.match(event.topic):
                    callbacks.append(callback)

        # Invoke without lock to prevent deadlocks
        for callback in callbacks:
            try:
                callback(event)
            except Exception as exc:
                self._invoke_error_handlers(callback.__name__, event, exc)

        return len(callbacks)

    def on_error(self, handler: Callable[[str, Event, Exception], None]) -> None:
        """Register global error handler for callback exceptions."""
        with self._lock:
            self._error_handlers.append(handler)

    def _invoke_error_handlers(self, callback_name: str, event: Event, exc: Exception):
        with self._lock:
            handlers = self._error_handlers.copy()
        for handler in handlers:
            try:
                handler(callback_name, event, exc)
            except Exception:
                pass  # Don't cascade error handler failures

    def unsubscribe_all(self, topic: str) -> int:
        """Remove all exact subscribers for topic."""
        with self._lock:
            count = len(self._subscribers.get(topic, []))
            self._subscribers.pop(topic, None)
            return count

    def clear(self):
        """Remove all subscribers."""
        with self._lock:
            self._subscribers.clear()
            self._wildcard_subscribers.clear()

    def stats(self):
        """Return subscriber counts."""
        with self._lock:
            exact_count = sum(len(v) for v in self._subscribers.values())
            wildcard_count = len(self._wildcard_subscribers)
        return {"exact": exact_count, "wildcard": wildcard_count}

# 1. Exact subscriptions
bus = EventBus()

def on_complete(event: Event):
    print(f"Job {event.data['id']} completed")

bus.subscribe("etl.pipeline.complete", on_complete)
bus.publish(Event("etl.pipeline.complete", {"id": "job-001"}))

# 2. Wildcard (prefix) subscriptions
def on_any_step(event: Event):
    print(f"Step: {event.topic}")

bus.subscribe("etl.step.*", on_any_step, MatchMode.PREFIX)
bus.publish(Event("etl.step.extract", {}))   # Matched
bus.publish(Event("etl.step.load", {}))      # Matched

# 3. Regex subscriptions
def on_errors(event: Event):
    print(f"Error: {event.data['message']}")

bus.subscribe(r"^etl\..*\.error$", on_errors, MatchMode.REGEX)
bus.publish(Event("etl.extract.error", {"message": "timeout"}))  # Matched

# 4. Error handling
def log_callback_error(callback_name: str, event: Event, exc: Exception):
    print(f"Callback {callback_name} failed on {event.topic}: {exc}")

bus.on_error(log_callback_error)

# 5. Dynamic unsubscribe
count = bus.unsubscribe_all("etl.pipeline.complete")
print(f"Removed {count} subscribers")

# 6. Stats
stats = bus.stats()  # {"exact": 5, "wildcard": 2}

async def publish_async(self, event: Event):
    with self._lock:
        # ... gather callbacks ...
    tasks = [asyncio.create_task(cb(event)) for cb in callbacks]
    await asyncio.gather(*tasks, return_exceptions=True)