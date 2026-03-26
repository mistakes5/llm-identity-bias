"""
Publish-Subscribe Event System
Wildcard rules (fnmatch-style):
  *  → any chars within a segment  ("user.*"  matches "user.login")
  ** → across all segments         ("**"      matches everything)
  ?  → any single character        ("order.?" matches "order.A")
"""

import fnmatch
import threading
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Subscription:
    pattern: str
    callback: Callable
    once: bool = False


class EventBus:
    def __init__(self):
        self._subscriptions: list[Subscription] = []
        self._lock = threading.Lock()

    # ── Subscribe ──────────────────────────────────────────────────────
    def subscribe(self, pattern: str, callback: Callable) -> Subscription:
        """Subscribe to events matching pattern. Returns a token for unsubscribe."""
        sub = Subscription(pattern=pattern, callback=callback)
        with self._lock:
            self._subscriptions.append(sub)
        return sub

    def once(self, pattern: str, callback: Callable) -> Subscription:
        """Subscribe for one delivery only — auto-removed after first match."""
        sub = Subscription(pattern=pattern, callback=callback, once=True)
        with self._lock:
            self._subscriptions.append(sub)
        return sub

    # ── Unsubscribe ────────────────────────────────────────────────────
    def unsubscribe(self, token: Subscription) -> bool:
        """Remove a subscription by its token. Returns True if it existed."""
        with self._lock:
            try:
                self._subscriptions.remove(token)
                return True
            except ValueError:
                return False

    def unsubscribe_all(self, pattern: str | None = None) -> int:
        """Remove all subscriptions (or only those matching pattern). Returns count removed."""
        with self._lock:
            before = len(self._subscriptions)
            if pattern is None:
                self._subscriptions.clear()
            else:
                self._subscriptions = [s for s in self._subscriptions if s.pattern != pattern]
            return before - len(self._subscriptions)

    # ── Publish ────────────────────────────────────────────────────────
    def publish(self, event: str, data: Any = None) -> int:
        """
        Fire all callbacks whose pattern matches event.
        Errors in one callback are caught so others still run.
        Returns the number of callbacks invoked.
        """
        with self._lock:
            candidates = list(self._subscriptions)   # snapshot — release lock before callbacks

        fired: list[Subscription] = []
        count = 0

        for sub in candidates:
            if fnmatch.fnmatchcase(event, sub.pattern):
                try:
                    sub.callback(event, data)
                    count += 1
                except Exception as exc:
                    print(f"[EventBus] Error in '{sub.pattern}' callback: {exc!r}")
                if sub.once:
                    fired.append(sub)

        if fired:
            with self._lock:
                for sub in fired:
                    try:
                        self._subscriptions.remove(sub)
                    except ValueError:
                        pass  # concurrent unsubscribe already removed it

        return count

    # ── Helpers ────────────────────────────────────────────────────────
    def listener_count(self, pattern: str | None = None) -> int:
        with self._lock:
            if pattern is None:
                return len(self._subscriptions)
            return sum(1 for s in self._subscriptions if s.pattern == pattern)

    def __repr__(self) -> str:
        return f"<EventBus subscriptions={self.listener_count()}>"

bus = EventBus()

# ── Exact subscription ──────────────────────────────────────────────────
def on_login(event, data):
    print(f"Login: {data['user']}")

token = bus.subscribe("user.login", on_login)
bus.publish("user.login", {"user": "alice"})    # → Login: alice
bus.publish("user.logout", {"user": "alice"})   # → (nothing, no match)

# ── Wildcard subscription ───────────────────────────────────────────────
def on_any_user(event, data):
    print(f"User event: {event}")

bus.subscribe("user.*", on_any_user)
bus.publish("user.login", {})    # → User event: user.login
bus.publish("user.logout", {})   # → User event: user.logout
bus.publish("order.placed", {})  # → (nothing)

# ── Catch-all wildcard ──────────────────────────────────────────────────
bus.subscribe("**", lambda e, d: print(f"All events: {e}"))

# ── One-time subscription ───────────────────────────────────────────────
bus.once("app.ready", lambda e, d: print("App is ready — fires once!"))
bus.publish("app.ready")   # fires
bus.publish("app.ready")   # silently skipped — already removed

# ── Unsubscribe ─────────────────────────────────────────────────────────
bus.unsubscribe(token)          # remove specific subscription
bus.unsubscribe_all("user.*")   # remove all subscriptions with this exact pattern
bus.unsubscribe_all()           # clear everything

print(bus.listener_count())     # 0

# Collect errors instead of printing them
errors = []
# ... in the try/except:
except Exception as exc:
    errors.append((sub, exc))

# After the loop:
if errors:
    raise ExceptionGroup("EventBus publish errors", [e for _, e in errors])