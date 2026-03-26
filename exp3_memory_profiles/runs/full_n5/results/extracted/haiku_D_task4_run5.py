import threading
import weakref
import fnmatch
from typing import Callable, Any, Dict, List
from dataclasses import dataclass
from collections import defaultdict


@dataclass
class Event:
    """Represents an event with name and data."""
    name: str
    data: Any = None


class EventBus:
    """
    Thread-safe pub/sub event system with wildcard subscription support.
    
    Key design features:
    - Pattern matching using Unix fnmatch (*, ?, [seq])
    - Automatic memory cleanup via weak references for instance methods
    - Thread-safe with fine-grained locking (handlers called outside lock)
    - Error collection and reporting for all handler failures
    """

    def __init__(self):
        self._subscribers: Dict[str, List[tuple]] = defaultdict(list)
        self._strong_refs: Dict[int, tuple] = {}
        self._lock = threading.RLock()
        self._handler_id_counter = 0

    def subscribe(
        self,
        pattern: str,
        handler: Callable[[Event], None],
        *,
        keep_alive: bool = False
    ) -> str:
        """Subscribe to events matching pattern. Returns subscription ID."""
        with self._lock:
            handler_id = self._handler_id_counter
            self._handler_id_counter += 1

            if keep_alive:
                # Strong reference for module-level functions
                self._strong_refs[handler_id] = (handler, pattern)
                self._subscribers[pattern].append((handler_id, None))
            else:
                # Weak reference for instance methods (prevents memory leaks)
                if hasattr(handler, '__self__'):
                    weak_self = weakref.ref(
                        handler.__self__,
                        self._make_cleanup(handler_id, pattern)
                    )
                    weak_method = (weak_self, handler.__func__)
                    self._subscribers[pattern].append((handler_id, weak_method))
                else:
                    # Unbound functions kept with strong ref
                    self._strong_refs[handler_id] = (handler, pattern)
                    self._subscribers[pattern].append((handler_id, None))

            return f"{pattern}#{handler_id}"

    def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe using ID returned by subscribe()."""
        try:
            pattern, handler_id_str = subscription_id.rsplit("#", 1)
            handler_id = int(handler_id_str)
        except (ValueError, AttributeError):
            return False

        with self._lock:
            if pattern not in self._subscribers:
                return False

            before = len(self._subscribers[pattern])
            self._subscribers[pattern] = [
                (hid, w) for hid, w in self._subscribers[pattern]
                if hid != handler_id
            ]
            self._strong_refs.pop(handler_id, None)
            if not self._subscribers[pattern]:
                del self._subscribers[pattern]
            return len(self._subscribers[pattern]) < before

    def publish(self, event_name: str, data: Any = None) -> int:
        """
        Publish event to all matching subscribers.
        Returns number of handlers called.
        Raises RuntimeError if any handler fails.
        """
        event = Event(name=event_name, data=data)
        handlers_to_call: List[tuple] = []

        with self._lock:
            for pattern in self._subscribers:
                if fnmatch.fnmatch(event_name, pattern):
                    for handler_id, weak_method in self._subscribers[pattern]:
                        if weak_method is None:
                            # Strong ref
                            if handler_id in self._strong_refs:
                                handler, _ = self._strong_refs[handler_id]
                                handlers_to_call.append((handler, pattern))
                        else:
                            # Weak ref to bound method
                            weak_self, func = weak_method
                            instance = weak_self()
                            if instance is not None:
                                handler = func.__get__(instance, type(instance))
                                handlers_to_call.append((handler, pattern))

        # Call handlers OUTSIDE lock to prevent deadlocks
        call_count = 0
        errors = []
        for handler, pattern in handlers_to_call:
            try:
                handler(event)
                call_count += 1
            except Exception as e:
                errors.append((pattern, handler.__qualname__, e))

        if errors:
            msg = f"Errors in {len(errors)} handler(s):\n"
            for pattern, handler_name, exc in errors:
                msg += f"  Pattern '{pattern}', {handler_name}: {exc}\n"
            raise RuntimeError(msg) from errors[0][2]

        return call_count

    def _make_cleanup(self, handler_id: int, pattern: str) -> Callable:
        """Create cleanup callback for weak-reference GC."""
        def cleanup(weak_ref):
            with self._lock:
                if pattern in self._subscribers:
                    self._subscribers[pattern] = [
                        (hid, w) for hid, w in self._subscribers[pattern]
                        if hid != handler_id
                    ]
                    if not self._subscribers[pattern]:
                        del self._subscribers[pattern]
        return cleanup

    def subscribers_for(self, event_name: str) -> int:
        """Count handlers that would receive this event."""
        with self._lock:
            count = 0
            for pattern in self._subscribers:
                if fnmatch.fnmatch(event_name, pattern):
                    count += len(self._subscribers[pattern])
            return count

    def patterns(self) -> List[str]:
        """List all active subscription patterns."""
        with self._lock:
            return list(self._subscribers.keys())

    def clear(self) -> None:
        """Clear all subscriptions."""
        with self._lock:
            self._subscribers.clear()
            self._strong_refs.clear()

# ============================================================================
# Example 1: Basic subscription and publish
# ============================================================================

bus = EventBus()

def on_user_created(event: Event):
    print(f"User created: {event.data}")

sub_id = bus.subscribe("user.created", on_user_created)
bus.publish("user.created", data={"id": 1, "name": "Alice"})
bus.unsubscribe(sub_id)


# ============================================================================
# Example 2: Wildcard patterns
# ============================================================================

def on_any_user_event(event: Event):
    print(f"User event: {event.name}")

# Matches: user.created, user.updated, user.deleted
bus.subscribe("user.*", on_any_user_event)
bus.publish("user.created", data={"id": 2})      # Matches
bus.publish("user.updated", data={"id": 2})      # Matches
bus.publish("order.created", data={"id": 100})   # No match


# ============================================================================
# Example 3: Class-based handlers with automatic cleanup
# ============================================================================

class UserService:
    def on_user_created(self, event: Event):
        print(f"Processing user {event.data.get('id')}")

service = UserService()

# Weak reference - automatically cleaned when service is deleted
bus.subscribe("user.*", service.on_user_created)
bus.publish("user.created", data={"id": 3})

del service  # Instance deleted → weak ref auto-cleaned
# Next publish won't call the deleted handler


# ============================================================================
# Example 4: Pattern variations
# ============================================================================

# Exact match
bus.subscribe("payment.completed", handler)

# Wildcard: matches payment.*, order.*, etc.
bus.subscribe("*.completed", handler)

# Match all
bus.subscribe("*", handler)

# Character ranges
bus.subscribe("user.[a-c]*", handler)  # user.activate, user.backup, etc.

# Question mark for single char
bus.subscribe("order.?", handler)  # order.a, order.1, etc.


# ============================================================================
# Example 5: Error handling
# ============================================================================

def broken_handler(event: Event):
    raise ValueError("Processing failed")

bus.subscribe("user.*", broken_handler)

try:
    bus.publish("user.created", data={"id": 4})
except RuntimeError as e:
    print(f"Handler error: {e}")
    # Output: Errors in 1 handler(s):
    #   Pattern 'user.*', broken_handler: Processing failed


# ============================================================================
# Example 6: Counting subscribers
# ============================================================================

count = bus.subscribers_for("user.created")  # How many would receive?
patterns = bus.patterns()                     # What patterns are active?