from typing import Any, Optional


class Node:
    """Doubly-linked list node for tracking order."""
    def __init__(self, key: Any, value: Any):
        self.key = key
        self.value = value
        self.prev: Optional[Node] = None
        self.next: Optional[Node] = None


class LRUCache:
    """
    LRU (Least Recently Used) Cache with O(1) get and put operations.

    Uses a combination of:
    - Dictionary: for O(1) key lookup and value access
    - Doubly-linked list: for O(1) removal and O(1) reordering

    Args:
        capacity: Maximum number of items to store in the cache
    """

    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("Capacity must be positive")

        self.capacity = capacity
        self.cache: dict[Any, Node] = {}  # key -> Node mapping

        # Sentinel nodes to avoid None checks during removal
        self.head = Node(None, None)  # Points to most recently used
        self.tail = Node(None, None)  # Points to least recently used
        self.head.next = self.tail
        self.tail.prev = self.head

    def get(self, key: Any) -> Any:
        """
        Get value by key and mark it as recently used.
        Time: O(1), Space: O(1)
        """
        if key not in self.cache:
            raise KeyError(f"Key '{key}' not found in cache")

        node = self.cache[key]
        self._move_to_front(node)  # Mark as recently used
        return node.value

    def put(self, key: Any, value: Any) -> None:
        """
        Add or update a key-value pair, marking it as recently used.
        If at capacity, evict the least recently used item.
        Time: O(1), Space: O(1) amortized
        """
        # If key exists, update it and move to front
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            self._move_to_front(node)
            return

        # Create new node for new key
        new_node = Node(key, value)
        self.cache[key] = new_node
        self._add_to_front(new_node)

        # Evict least recently used if over capacity
        if len(self.cache) > self.capacity:
            self._evict_least_recent()

    def _move_to_front(self, node: Node) -> None:
        """Remove node from its current position and add it to the front."""
        self._remove(node)
        self._add_to_front(node)

    def _add_to_front(self, node: Node) -> None:
        """Add node right after head (most recently used position)."""
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node

    def _remove(self, node: Node) -> None:
        """Remove node from the linked list."""
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node

    def _evict_least_recent(self) -> None:
        """Remove the least recently used item (just before tail)."""
        lru_node = self.tail.prev
        self._remove(lru_node)
        del self.cache[lru_node.key]

    def __repr__(self) -> str:
        """Display cache contents from most to least recent."""
        items = []
        node = self.head.next
        while node != self.tail:
            items.append(f"{node.key}: {node.value}")
            node = node.next
        return f"LRUCache({', '.join(items)})"

    def __len__(self) -> int:
        """Return current number of items in cache."""
        return len(self.cache)


# ============================================================================
# Example Usage
# ============================================================================

if __name__ == "__main__":
    # Initialize cache with capacity of 2
    cache = LRUCache(capacity=2)

    print("=== Basic Operations ===")
    cache.put("a", 1)
    cache.put("b", 2)
    print(f"Cache: {cache}")

    print(f"get('a'): {cache.get('a')}")  # Returns 1, moves 'a' to front
    print(f"After get('a'): {cache}")

    print("\n=== Eviction (Over Capacity) ===")
    cache.put("c", 3)  # Should evict 'b' (least recently used)
    print(f"After put('c', 3): {cache}")

    print("\n=== Full Sequence Test ===")
    cache2 = LRUCache(capacity=3)
    
    cache2.put("x", 1)
    cache2.put("y", 2)
    cache2.put("z", 3)
    print(f"After 3 puts: {cache2}")
    
    val = cache2.get("x")  # Move 'x' to front
    print(f"get('x'): {val}, cache now: {cache2}")
    
    cache2.put("w", 4)  # Evict 'y' (least recent)
    print(f"After put('w', 4): {cache2}")