from typing import Any, Optional


class Node:
    """Node in the doubly-linked list."""
    def __init__(self, key: Any = None, value: Any = None):
        self.key = key
        self.value = value
        self.prev: Optional['Node'] = None
        self.next: Optional['Node'] = None


class LRUCache:
    """
    Least Recently Used Cache with O(1) get and put operations.

    Uses a doubly-linked list to track access order + hash map for lookups.
    - Front (head.next) = most recently used
    - Back (tail.prev) = least recently used
    """

    def __init__(self, capacity: int):
        """Initialize cache with fixed capacity."""
        if capacity <= 0:
            raise ValueError("Capacity must be positive")

        self.capacity = capacity
        self.cache: dict[Any, Node] = {}  # key -> Node mapping

        # Sentinel nodes to avoid edge cases
        self.head = Node()  # dummy head (always present)
        self.tail = Node()  # dummy tail (always present)
        self.head.next = self.tail
        self.tail.prev = self.head

    def get(self, key: Any) -> Any:
        """
        Get value by key. Mark the key as recently used.
        Time: O(1), Space: O(1)
        """
        if key not in self.cache:
            return -1  # convention: return -1 for missing keys

        node = self.cache[key]
        self._move_to_front(node)  # Mark as recently used
        return node.value

    def put(self, key: Any, value: Any) -> None:
        """
        Put key-value pair. If key exists, update value.
        If cache is full, evict the least recently used item.
        Time: O(1), Space: O(1)
        """
        if key in self.cache:
            # Update existing key
            node = self.cache[key]
            node.value = value
            self._move_to_front(node)
        else:
            # Add new key
            if len(self.cache) >= self.capacity:
                # Evict least recently used (node right before tail)
                self._remove_node(self.tail.prev)

            # Add new node at front (after head)
            new_node = Node(key, value)
            self.cache[key] = new_node
            self._add_to_front(new_node)

    def _move_to_front(self, node: Node) -> None:
        """Move node to front (most recently used position)."""
        self._remove_node(node)
        self._add_to_front(node)

    def _add_to_front(self, node: Node) -> None:
        """Add node right after head (most recently used)."""
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node

    def _remove_node(self, node: Node) -> None:
        """Remove node from linked list."""
        node.prev.next = node.next
        node.next.prev = node.prev
        if node.key in self.cache:
            del self.cache[node.key]


# Usage Example
if __name__ == '__main__':
    cache = LRUCache(2)

    cache.put(1, 'a')
    cache.put(2, 'b')
    print(cache.get(1))  # Returns 'a'

    cache.put(3, 'c')  # Evicts key 2
    print(cache.get(2))  # Returns -1 (not found)

    cache.put(4, 'd')  # Evicts key 1
    print(cache.get(1))  # Returns -1 (not found)
    print(cache.get(3))  # Returns 'c'
    print(cache.get(4))  # Returns 'd'