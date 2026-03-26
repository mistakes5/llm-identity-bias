import fnmatch
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Subscription:
    """Represents a single event subscription."""
    id: str
    pattern: str
    callback: Callable[[str, Any], None]
    once: bool = False


class EventBus:
    """
    A publish-subscribe event bus with wildcard pattern support.

    Wildcard rules (via fnmatch):
        *   matches any characters within a single segment  (e.g. "user.*")
        **  not natively supported — use "*" for broad matching  (e.g. "order.*")
        ?   matches any single character

    Examples:
        bus = EventBus()
        sub_id = bus.subscribe("user.created", handler)
        sub_id = bus.subscribe("user.*",       handler)   # wildcard
        sub_id = bus.subscribe("*",            handler)   # catch-all
        bus.publish("user.created", {"id": 42})
        bus.unsubscribe(sub_id)
    """

    def __init__(self) -> None:
        # pattern → {sub_id → Subscription}
        self._subscriptions: dict[str, dict[str, Subscription]] = defaultdict(dict)

    # ------------------------------------------------------------------ #
    #  Subscribing                                                         #
    # ------------------------------------------------------------------ #

    def subscribe(
        self,
        pattern: str,
        callback: Callable[[str, Any], None],
        *,
        once: bool = False,
    ) -> str:
        """
        Subscribe to events matching *pattern*.

        Args:
            pattern:  Exact event name or fnmatch wildcard pattern.
            callback: Called as callback(event_name, data) on match.
            once:     If True, the subscription fires once then auto-removes.

        Returns:
            A subscription ID string usable with unsubscribe().
        """
        sub_id = str(uuid.uuid4())
        self._subscriptions[pattern][sub_id] = Subscription(
            id=sub_id, pattern=pattern, callback=callback, once=once
        )
        return sub_id

    def once(self, pattern: str, callback: Callable[[str, Any], None]) -> str:
        """Convenience wrapper — subscribe for exactly one delivery."""
        return self.subscribe(pattern, callback, once=True)

    # ------------------------------------------------------------------ #
    #  Unsubscribing                                                       #
    # ------------------------------------------------------------------ #

    def unsubscribe(self, sub_id: str) -> bool:
        """
        Remove a subscription by ID.

        Returns:
            True if found and removed, False if not found.
        """
        for pattern, subs in list(self._subscriptions.items()):
            if sub_id in subs:
                del subs[sub_id]
                if not subs:                        # prune empty buckets
                    del self._subscriptions[pattern]
                return True
        return False

    def clear(self, pattern: str | None = None) -> None:
        """Remove all subscriptions, or only those for a specific pattern."""
        if pattern is None:
            self._subscriptions.clear()
        elif pattern in self._subscriptions:
            del self._subscriptions[pattern]

    # ------------------------------------------------------------------ #
    #  Publishing                                                          #
    # ------------------------------------------------------------------ #

    def publish(self, event: str, data: Any = None) -> int:
        """
        Publish *event* with optional *data* to all matching subscribers.

        Pattern matching is performed with fnmatch, so wildcard patterns
        registered via subscribe() are evaluated against the concrete
        event name passed here.

        Returns:
            Number of subscriber callbacks that were invoked.
        """
        notified = 0
        once_ids: list[str] = []

        for pattern, subs in list(self._subscriptions.items()):
            if fnmatch.fnmatch(event, pattern):
                for sub_id, sub in list(subs.items()):
                    try:
                        sub.callback(event, data)
                    except Exception as exc:
                        # Isolate subscriber errors so other subs still fire
                        print(f"[EventBus] Error in subscriber {sub_id}: {exc}")
                    notified += 1
                    if sub.once:
                        once_ids.append(sub_id)

        for sub_id in once_ids:
            self.unsubscribe(sub_id)

        return notified

    # ------------------------------------------------------------------ #
    #  Introspection                                                       #
    # ------------------------------------------------------------------ #

    def listener_count(self, event: str) -> int:
        """Return how many subscribers would receive *event* right now."""
        return sum(
            len(subs)
            for pattern, subs in self._subscriptions.items()
            if fnmatch.fnmatch(event, pattern)
        )

    @property
    def patterns(self) -> list[str]:
        """All currently registered patterns."""
        return list(self._subscriptions.keys())


# ------------------------------------------------------------------ #
#  Usage demonstration                                                #
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    bus = EventBus()
    log: list[str] = []

    # --- exact subscription -------------------------------------------
    def on_user_created(event: str, data: Any) -> None:
        log.append(f"exact    | {event} → {data}")

    # --- wildcard subscription ----------------------------------------
    def on_any_user(event: str, data: Any) -> None:
        log.append(f"wildcard | {event} → {data}")

    # --- catch-all subscription ---------------------------------------
    def on_everything(event: str, data: Any) -> None:
        log.append(f"catch-all| {event} → {data}")

    sub_exact    = bus.subscribe("user.created",  on_user_created)
    sub_wildcard = bus.subscribe("user.*",         on_any_user)
    sub_all      = bus.subscribe("*",              on_everything)

    # publish — all three handlers fire
    print("=== publish: user.created ===")
    bus.publish("user.created", {"id": 1, "name": "Alice"})
    for entry in log:
        print(" ", entry)
    log.clear()

    # publish — only wildcard + catch-all fire
    print("\n=== publish: user.deleted ===")
    bus.publish("user.deleted", {"id": 1})
    for entry in log:
        print(" ", entry)
    log.clear()

    # publish — only catch-all fires (order.* doesn't match user.*)
    print("\n=== publish: order.placed ===")
    bus.publish("order.placed", {"order_id": 99})
    for entry in log:
        print(" ", entry)
    log.clear()

    # unsubscribe the wildcard handler
    bus.unsubscribe(sub_wildcard)
    print("\n=== after unsubscribing wildcard: publish user.updated ===")
    bus.publish("user.updated", {"id": 1})
    for entry in log:
        print(" ", entry)
    log.clear()

    # once() — fires exactly once then self-removes
    fired: list[str] = []
    bus.once("session.start", lambda e, d: fired.append(e))
    bus.publish("session.start", {})   # fires
    bus.publish("session.start", {})   # silently dropped
    print(f"\n=== once() fired {len(fired)} time(s) (expected 1) ===")

    # introspection
    print(f"\nlistener_count('user.created') = {bus.listener_count('user.created')}")
    print(f"registered patterns            = {bus.patterns}")