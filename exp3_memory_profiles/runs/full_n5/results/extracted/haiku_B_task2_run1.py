from typing import Optional, Any


class Node:
    """Node in a doubly-linked list, stores key-value pair."""
    def __init__(self, key: int, value: Any):
        self.key = key
        self.value = value
        self.prev: Optional['Node'] = None
        self.next: Optional['Node'] = None


class LRUCache:
    """
    LRU (Least Recently Used) Cache with O(1) get and put operations.

    Architecture:
    - Hash map: O(1) key lookup → node reference
    - Doubly-linked list: O(1) insertion/deletion + maintains usage order
      * Tail (right): most recently used
      * Head (left): least recently used (evicted when capacity exceeded)
    """

    def __init__(self, capacity: int):
        """Initialize cache with fixed capacity."""
        if capacity <= 0:
            raise ValueError("Capacity must be positive")

        self.capacity = capacity
        self.cache: dict[int, Node] = {}  # Maps key → Node

        # Sentinel nodes (dummy nodes) avoid null checks in the linked list
        self.head = Node(0, 0)  # Marks the "least recently used" end
        self.tail = Node(0, 0)  # Marks the "most recently used" end
        self.head.next = self.tail
        self.tail.prev = self.head

    def get(self, key: int) -> int:
        """
        Get value by key. Marks the key as recently used.

        Time: O(1)
        Space: O(1)
        """
        if key not in self.cache:
            return -1

        node = self.cache[key]
        self._move_to_tail(node)  # Mark as recently used
        return node.value

    def put(self, key: int, value: Any) -> None:
        """
        Insert or update a key-value pair. Marks the key as recently used.
        If cache is full, evicts the least recently used item.

        Time: O(1)
        Space: O(1)
        """
        if key in self.cache:
            # Key exists: update value and mark as recently used
            node = self.cache[key]
            node.value = value
            self._move_to_tail(node)
        else:
            # Key is new: add to cache
            new_node = Node(key, value)
            self.cache[key] = new_node
            self._add_to_tail(new_node)

            # If over capacity, evict least recently used (head.next)
            if len(self.cache) > self.capacity:
                lru_node = self.head.next
                self._remove_node(lru_node)
                del self.cache[lru_node.key]

    def _move_to_tail(self, node: Node) -> None:
        """Remove node from current position and add to tail (most recent)."""
        self._remove_node(node)
        self._add_to_tail(node)

    def _add_to_tail(self, node: Node) -> None:
        """Add node right before tail, marking it as most recently used."""
        node.prev = self.tail.prev
        node.next = self.tail
        self.tail.prev.next = node
        self.tail.prev = node

    def _remove_node(self, node: Node) -> None:
        """Remove node from its current position in the linked list."""
        node.prev.next = node.next
        node.next.prev = node.prev

    def __repr__(self) -> str:
        """Return string representation of cache (head→tail order)."""
        result = []
        current = self.head.next
        while current != self.tail:
            result.append(f"{current.key}:{current.value}")
            current = current.next
        return f"LRUCache({', '.join(result)})"


# Example Usage
if __name__ == "__main__":
    cache = LRUCache(2)
    
    # Insert two items
    cache.put(1, "a")
    cache.put(2, "b")
    print(cache)  # LRUCache(1:a, 2:b)
    
    # Access item 1 (marks it as recently used)
    print(cache.get(1))  # Returns "a"
    # Now 2 is least recently used
    
    # Add new item, evicts 2
    cache.put(3, "c")
    print(cache)  # LRUCache(1:a, 3:c)
    
    print(cache.get(2))  # Returns -1 (evicted)

cache = LRUCache(2)
cache.put(1, 'a')          # [1:a]
cache.put(2, 'b')          # [1:a, 2:b]
cache.get(1)               # [2:b, 1:a]  ← 1 moves to end (most recent)
cache.put(3, 'c')          # [1:a, 3:c]  ← 2 evicted (was least recent)
cache.get(2)               # -1 (not found)