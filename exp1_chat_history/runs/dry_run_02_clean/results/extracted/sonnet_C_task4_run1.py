import fnmatch
from collections import defaultdict
from typing import Callable, Any


class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event: str, handler: Callable) -> None:
        """Subscribe a handler to an event (supports wildcards like 'user.*')."""
        self._subscribers[event].append(handler)

    def unsubscribe(self, event: str, handler: Callable) -> None:
        """Unsubscribe a handler from an event."""
        handlers = self._subscribers.get(event, [])
        if handler in handlers:
            handlers.remove(handler)
            if not handlers:
                del self._subscribers[event]

    def publish(self, event: str, data: Any = None) -> int:
        """
        Publish an event with optional data.
        Notifies all handlers whose subscription pattern matches the event.
        Returns the number of handlers notified.
        """
        notified = 0
        for pattern, handlers in list(self._subscribers.items()):
            if fnmatch.fnmatch(event, pattern):
                for handler in handlers:
                    handler(event, data)
                    notified += 1
        return notified

    def subscribers(self, event: str) -> list[Callable]:
        """Return all handlers subscribed to an exact pattern."""
        return list(self._subscribers.get(event, []))

    def clear(self, event: str = None) -> None:
        """Clear all handlers for a specific event, or all events if None."""
        if event is None:
            self._subscribers.clear()
        elif event in self._subscribers:
            del self._subscribers[event]


# ── Demo ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    bus = EventBus()

    # Basic subscription
    def on_login(event, data):
        print(f"[{event}] User logged in: {data['username']}")

    def on_any_user(event, data):
        print(f"[WILDCARD {event}] caught by user.* handler")

    def on_everything(event, data):
        print(f"[GLOBAL *] event='{event}' data={data}")

    bus.subscribe("user.login", on_login)
    bus.subscribe("user.*", on_any_user)   # wildcard: all user events
    bus.subscribe("*", on_everything)      # wildcard: every event

    print("=== Publish user.login ===")
    bus.publish("user.login", {"username": "alice"})

    print("\n=== Publish user.logout ===")
    bus.publish("user.logout", {"username": "alice"})

    print("\n=== Publish order.placed ===")
    bus.publish("order.placed", {"item": "book", "qty": 2})

    # Unsubscribe
    print("\n=== Unsubscribe on_login, then publish user.login again ===")
    bus.unsubscribe("user.login", on_login)
    bus.publish("user.login", {"username": "bob"})

    # No handlers
    print("\n=== Publish unknown.event (only global wildcard catches it) ===")
    count = bus.publish("unknown.event", None)
    print(f"Handlers notified: {count}")