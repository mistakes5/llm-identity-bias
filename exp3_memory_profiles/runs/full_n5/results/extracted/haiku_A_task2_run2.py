"""
LRU (Least Recently Used) Cache Implementation

Design:
- Hash Map (dict): O(1) key lookups
- Doubly-Linked List: Maintains access order (most recent at head, least recent at tail)

Time Complexity:
- get(key): O(1) - dict lookup + list node movement
- put(key, value): O(1) - dict operation + list manipulation
- Space Complexity: O(capacity)
"""

from typing import TypeVar, Generic, Optional

K = TypeVar('K')
V = TypeVar('V')


class Node(Generic[K, V]):
    """Node in the doubly-linked list."""

    def __init__(self, key: K, value: V):
        self.key = key
        self.value = value
        self.prev: Optional[Node[K, V]] = None
        self.next: Optional[Node[K, V]] = None


class LRUCache(Generic[K, V]):
    """
    LRU Cache with O(1) get and put operations.

    Most recently used items are near the head.
    Least recently used items are near the tail (evicted first).
    """

    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("Capacity must be positive")

        self.capacity = capacity
        self.cache: dict[K, Node[K, V]] = {}

        # Dummy nodes for easier list manipulation (no bounds checking)
        self.head: Node[K, V] = Node(None, None)  # type: ignore
        self.tail: Node[K, V] = Node(None, None)  # type: ignore
        self.head.next = self.tail
        self.tail.prev = self.head

    def _move_to_head(self, node: Node[K, V]) -> None:
        """Move a node to the head (mark as most recently used)."""
        # Remove node from current position
        node.prev.next = node.next
        node.next.prev = node.prev

        # Insert at head
        node.next = self.head.next
        node.prev = self.head
        self.head.next.prev = node
        self.head.next = node

    def _remove_tail(self) -> None:
        """Remove the tail node (least recently used)."""
        lru_node = self.tail.prev
        del self.cache[lru_node.key]

        lru_node.prev.next = self.tail
        self.tail.prev = lru_node.prev

    def get(self, key: K) -> Optional[V]:
        """
        Retrieve a value by key in O(1).

        If key exists, mark it as recently used and return value.
        """
        if key not in self.cache:
            return None

        node = self.cache[key]
        self._move_to_head(node)  # Mark as recently used
        return node.value

    def put(self, key: K, value: V) -> None:
        """
        Insert or update a key-value pair in O(1).

        If key exists, update value and mark as recently used.
        If cache is at capacity, evict the least recently used item first.
        """
        if key in self.cache:
            # Update existing key
            node = self.cache[key]
            node.value = value
            self._move_to_head(node)
        else:
            # Add new key
            if len(self.cache) >= self.capacity:
                self._remove_tail()

            new_node = Node(key, value)
            self.cache[key] = new_node
            self._move_to_head(new_node)

# Create a cache with capacity 3
cache = LRUCache(3)

# Put items
cache.put("user:1", {"id": 1, "name": "Alice"})
cache.put("user:2", {"id": 2, "name": "Bob"})
cache.put("user:3", {"id": 3, "name": "Charlie"})

# Get item (marks as recently used)
print(cache.get("user:1"))  # {"id": 1, "name": "Alice"}

# Add new item, evicts least recently used ("user:2")
cache.put("user:4", {"id": 4, "name": "Diana"})

# user:2 is gone
print(cache.get("user:2"))  # None