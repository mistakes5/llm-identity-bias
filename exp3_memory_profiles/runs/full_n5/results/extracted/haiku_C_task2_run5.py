from typing import Optional


class Node:
    """Doubly linked list node for LRU cache."""

    def __init__(self, key: int, value: int):
        self.key = key
        self.value = value
        self.prev: Optional['Node'] = None
        self.next: Optional['Node'] = None


class LRUCache:
    """
    LRU (Least Recently Used) Cache with O(1) get and put operations.

    Uses a combination of:
    - HashMap: for O(1) key lookups and value retrieval
    - Doubly Linked List: for O(1) reordering of access order
    """

    def __init__(self, capacity: int):
        """Initialize the LRU cache."""
        if capacity <= 0:
            raise ValueError("Capacity must be positive")

        self.capacity = capacity
        self.cache: dict[int, Node] = {}  # key -> Node mapping

        # Dummy nodes to simplify edge cases
        self.head = Node(0, 0)  # Least recently used (LRU end)
        self.tail = Node(0, 0)  # Most recently used (MRU end)
        self.head.next = self.tail
        self.tail.prev = self.head

    def get(self, key: int) -> int:
        """Get value in O(1). Accessing marks key as recently used."""
        if key not in self.cache:
            return -1

        node = self.cache[key]
        self._move_to_end(node)  # Mark as recently used
        return node.value

    def put(self, key: int, value: int) -> None:
        """Add/update value in O(1). Evicts LRU if at capacity."""
        # Key exists: update and mark as recent
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            self._move_to_end(node)
            return

        # New key: check capacity
        if len(self.cache) == self.capacity:
            self._evict_lru()

        # Add new node
        new_node = Node(key, value)
        self.cache[key] = new_node
        self._add_to_end(new_node)

    def _move_to_end(self, node: Node) -> None:
        """Move node to end (mark as most recently used)."""
        self._remove_node(node)
        self._add_to_end(node)

    def _remove_node(self, node: Node) -> None:
        """Remove node from linked list."""
        node.prev.next = node.next
        node.next.prev = node.prev

    def _add_to_end(self, node: Node) -> None:
        """Add node to end (before tail)."""
        node.prev = self.tail.prev
        node.next = self.tail
        self.tail.prev.next = node
        self.tail.prev = node

    def _evict_lru(self) -> None:
        """Remove least recently used (head.next)."""
        lru_node = self.head.next
        self._remove_node(lru_node)
        del self.cache[lru_node.key]


# ============================================================================
# Usage Examples
# ============================================================================

if __name__ == "__main__":
    # Example 1: Basic operations
    print("Example 1: Basic LRU Cache")
    cache = LRUCache(capacity=2)
    cache.put(1, "Alice")
    cache.put(2, "Bob")
    print(f"get(1) = {cache.get(1)}")    # Returns "Alice", marks 1 as recent
    cache.put(3, "Charlie")               # Evicts key 2 (least recent)
    print(f"get(2) = {cache.get(2)}")    # Returns -1 (evicted)
    print(f"Keys in cache: {list(cache.cache.keys())}")  # [1, 3]

    # Example 2: Update existing key
    print("\nExample 2: Updating existing key")
    cache2 = LRUCache(2)
    cache2.put(1, 10)
    cache2.put(2, 20)
    cache2.put(1, 100)  # Update key 1
    print(f"get(1) = {cache2.get(1)}")  # Returns 100
    cache2.put(3, 30)   # Evicts key 2, not 1
    print(f"get(2) = {cache2.get(2)}")  # Returns -1 (evicted)
    print(f"get(1) = {cache2.get(1)}")  # Returns 100 (still exists)