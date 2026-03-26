from typing import Optional


class Node:
    """Doubly linked list node for maintaining LRU order."""
    def __init__(self, key: int, value: int):
        self.key = key
        self.value = value
        self.prev: Optional['Node'] = None
        self.next: Optional['Node'] = None


class LRUCache:
    """
    LRU Cache with O(1) get and put operations.

    Uses a doubly-linked list to track usage order and a hash map for O(1) lookups.
    - Most recently used items are at the END of the list
    - Least recently used items are at the HEAD of the list
    """

    def __init__(self, capacity: int):
        """Initialize the LRU cache."""
        self.capacity = capacity
        self.cache: dict[int, Node] = {}  # key -> Node

        # Sentinel nodes to avoid null checks
        self.head = Node(0, 0)  # Least recently used end
        self.tail = Node(0, 0)  # Most recently used end
        self.head.next = self.tail
        self.tail.prev = self.head

    def get(self, key: int) -> int:
        """Retrieve value and mark as recently used. O(1) time."""
        if key not in self.cache:
            return -1

        node = self.cache[key]
        self._move_to_end(node)  # Mark as most recently used
        return node.value

    def put(self, key: int, value: int) -> None:
        """Insert or update a key-value pair. Evicts LRU on overflow. O(1) time."""
        if key in self.cache:
            # Update existing key
            node = self.cache[key]
            node.value = value
            self._move_to_end(node)
        else:
            # Insert new key
            if len(self.cache) >= self.capacity:
                self._evict_lru()

            node = Node(key, value)
            self.cache[key] = node
            self._add_to_end(node)

    def _move_to_end(self, node: Node) -> None:
        """Remove node and re-add at end (most recent position)."""
        self._remove_node(node)
        self._add_to_end(node)

    def _add_to_end(self, node: Node) -> None:
        """Add node right before tail (most recently used position)."""
        node.prev = self.tail.prev
        node.next = self.tail
        self.tail.prev.next = node
        self.tail.prev = node

    def _remove_node(self, node: Node) -> None:
        """Remove node from linked list."""
        if node.prev:
            node.prev.next = node.next
        if node.next:
            node.next.prev = node.prev

    def _evict_lru(self) -> None:
        """Remove least recently used item (right after head)."""
        lru_node = self.head.next
        self._remove_node(lru_node)
        del self.cache[lru_node.key]

# Create cache with capacity 2
cache = LRUCache(2)

cache.put(1, 1)      # Cache: [1:1]
cache.put(2, 2)      # Cache: [1:1, 2:2]

cache.get(1)         # Returns 1, moves 1 to end
                     # Cache: [2:2, 1:1]  (1 is now most recent)

cache.put(3, 3)      # Capacity exceeded, evict 2 (LRU)
                     # Cache: [1:1, 3:3]

cache.get(2)         # Returns -1 (evicted)

cache.put(1, 10)     # Update value, move to end
                     # Cache: [3:3, 1:10]