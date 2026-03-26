from typing import Optional, Any


class Node:
    """Doubly-linked list node."""
    def __init__(self, key: Any, value: Any):
        self.key = key
        self.value = value
        self.prev: Optional['Node'] = None
        self.next: Optional['Node'] = None


class LRUCache:
    """O(1) LRU cache with fixed capacity.

    Uses:
    - HashMap (dict) for O(1) key lookups
    - Doubly-linked list for O(1) eviction and reordering

    Invariants:
    - Tail node is most recently used
    - Head node is least recently used (first to evict)
    - Both get() and put() promote accessed/inserted items to tail
    """

    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        self.capacity = capacity
        self.cache: dict[Any, Node] = {}

        # Sentinel nodes eliminate edge-case handling
        self.head = Node(None, None)
        self.tail = Node(None, None)
        self.head.next = self.tail
        self.tail.prev = self.head

    def get(self, key: Any) -> Optional[Any]:
        """Retrieve value and mark as recently used. O(1)."""
        if key not in self.cache:
            return None

        node = self.cache[key]
        self._move_to_tail(node)
        return node.value

    def put(self, key: Any, value: Any) -> None:
        """Insert or update key-value pair. O(1)."""
        # Update existing key
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            self._move_to_tail(node)
            return

        # Evict LRU if at capacity
        if len(self.cache) == self.capacity:
            lru_node = self.head.next
            self._remove_node(lru_node)
            del self.cache[lru_node.key]

        # Add new node to tail
        new_node = Node(key, value)
        self.cache[key] = new_node
        self._add_to_tail(new_node)

    def _move_to_tail(self, node: Node) -> None:
        """Move node to tail (mark as recently used). O(1)."""
        self._remove_node(node)
        self._add_to_tail(node)

    def _remove_node(self, node: Node) -> None:
        """Unlink node from list. O(1)."""
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node

    def _add_to_tail(self, node: Node) -> None:
        """Insert node before tail sentinel. O(1)."""
        prev_node = self.tail.prev
        prev_node.next = node
        node.prev = prev_node
        node.next = self.tail
        self.tail.prev = node


# Test
if __name__ == "__main__":
    cache = LRUCache(capacity=2)

    cache.put(1, "a")
    cache.put(2, "b")
    assert cache.get(1) == "a"  # Mark 1 as recent

    cache.put(3, "c")  # Evicts 2 (LRU)
    assert cache.get(2) is None
    assert cache.get(1) == "a"
    assert cache.get(3) == "c"

    cache.put(1, "a_updated")  # Update + move to tail
    cache.put(4, "d")  # Evicts 3
    assert cache.get(3) is None
    assert cache.get(4) == "d"
    assert cache.get(1) == "a_updated"

    print("✓ All tests passed")