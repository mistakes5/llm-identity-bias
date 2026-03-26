import fnmatch
from collections import defaultdict
from typing import Any, Callable

# Type alias for clarity
Handler = Callable[..., Any]


class EventBus:
    """
    A publish-subscribe event system with wildcard subscription support.

    Wildcard patterns follow Unix shell-style matching (via fnmatch):
      *   matches any sequence of characters (within a single segment)
      **  matches everything including dots
      ?   matches any single character
      [seq] matches any character in seq

    Examples:
      "user.*"      → matches "user.created", "user.deleted"
      "order.*.paid" → matches "order.web.paid", "order.mobile.paid"
      "*"           → matches everything
    """

    def __init__(self) -> None:
        # Exact event → list of handlers
        self._exact: dict[str, list[Handler]] = defaultdict(list)
        # Wildcard pattern → list of handlers
        self._wildcard: list[tuple[str, Handler]] = []

    # ------------------------------------------------------------------ #
    #  Subscribe                                                           #
    # ------------------------------------------------------------------ #

    def subscribe(self, event: str, handler: Handler) -> None:
        """Register *handler* to be called whenever *event* is published.

        If *event* contains glob characters ('*', '?', '[') it is treated
        as a wildcard pattern and matched against every future publish call.
        """
        if _is_pattern(event):
            self._wildcard.append((event, handler))
        else:
            self._exact[event].append(handler)

    # Convenience alias so the API reads naturally
    on = subscribe

    # ------------------------------------------------------------------ #
    #  Unsubscribe                                                         #
    # ------------------------------------------------------------------ #

    def unsubscribe(self, event: str, handler: Handler) -> bool:
        """Remove *handler* from *event*.  Returns True if found and removed."""
        if _is_pattern(event):
            before = len(self._wildcard)
            self._wildcard = [
                (pat, h) for pat, h in self._wildcard
                if not (pat == event and h is handler)
            ]
            return len(self._wildcard) < before
        else:
            handlers = self._exact.get(event, [])
            try:
                handlers.remove(handler)
                return True
            except ValueError:
                return False

    # ------------------------------------------------------------------ #
    #  Publish                                                             #
    # ------------------------------------------------------------------ #

    def publish(self, event: str, *args: Any, **kwargs: Any) -> int:
        """Emit *event*, forwarding *args* and *kwargs* to every subscriber.

        Returns the number of handlers that were called.
        """
        called = 0

        # 1. Exact-match subscribers
        for handler in list(self._exact.get(event, [])):
            handler(event, *args, **kwargs)
            called += 1

        # 2. Wildcard subscribers whose pattern matches this event
        for pattern, handler in list(self._wildcard):
            if fnmatch.fnmatch(event, pattern):
                handler(event, *args, **kwargs)
                called += 1

        return called

    # Convenience alias
    emit = publish

    # ------------------------------------------------------------------ #
    #  Introspection helpers                                               #
    # ------------------------------------------------------------------ #

    def listeners(self, event: str) -> list[Handler]:
        """Return all handlers that would fire for *event* (exact + wildcard)."""
        exact = list(self._exact.get(event, []))
        wildcards = [h for pat, h in self._wildcard if fnmatch.fnmatch(event, pat)]
        return exact + wildcards

    def clear(self, event: str | None = None) -> None:
        """Remove all handlers for *event*, or every handler if None."""
        if event is None:
            self._exact.clear()
            self._wildcard.clear()
        elif _is_pattern(event):
            self._wildcard = [(p, h) for p, h in self._wildcard if p != event]
        else:
            self._exact.pop(event, None)


# ------------------------------------------------------------------ #
#  Internal helpers                                                    #
# ------------------------------------------------------------------ #

def _is_pattern(event: str) -> bool:
    return any(ch in event for ch in ("*", "?", "["))


# ------------------------------------------------------------------ #
#  Demo                                                                #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    bus = EventBus()

    # --- Exact subscriptions ---
    def on_user_created(event, user):
        print(f"[exact]    {event} → welcome, {user['name']}!")

    def on_order_paid(event, order_id, amount):
        print(f"[exact]    {event} → order #{order_id} paid ${amount:.2f}")

    bus.subscribe("user.created", on_user_created)
    bus.subscribe("order.paid",   on_order_paid)

    # --- Wildcard subscriptions ---
    def audit_log(event, *args, **kwargs):
        print(f"[wildcard] audit: {event!r}  args={args} kwargs={kwargs}")

    def user_events(event, *args, **kwargs):
        print(f"[wildcard] user-listener: {event!r}")

    bus.subscribe("*",      audit_log)     # catches EVERYTHING
    bus.subscribe("user.*", user_events)   # catches all user.* events

    print("=" * 55)
    print("Publishing 'user.created'")
    print("=" * 55)
    bus.publish("user.created", {"name": "Alice", "id": 1})

    print()
    print("=" * 55)
    print("Publishing 'order.paid'")
    print("=" * 55)
    bus.publish("order.paid", order_id=42, amount=99.95)

    print()
    print("=" * 55)
    print("Unsubscribing audit_log from '*', then re-publishing")
    print("=" * 55)
    bus.unsubscribe("*", audit_log)
    n = bus.publish("user.created", {"name": "Bob", "id": 2})
    print(f"  → {n} handler(s) fired")

    print()
    print(f"Listeners for 'user.created': {bus.listeners('user.created')}")