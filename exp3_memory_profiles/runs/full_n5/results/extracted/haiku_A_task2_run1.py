"""
LRU (Least Recently Used) Cache implementation with O(1) get and put operations.

Design:
- Dictionary for O(1) key lookups
- Doubly-linked list to maintain access order (most recent at end, least recent at head)
- When accessed/updated, move node to the end (mark as most recently used)
- When capacity exceeded, evict from the head (least recently used)
"""


class Node:
    """Node in the doubly-linked list."""
    def __init__(self, key: int, value: int):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class LRUCache:
    """
    LRU Cache with O(1) get and put operations.

    Capacity: Fixed number of items. When exceeded, evicts least recently used.
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = {}  # key -> Node (for O(1) lookup)

        # Doubly-linked list with sentinel head and tail for simplicity
        # Head.next points to most recently evictable (least recently used)
        # Tail.prev points to most recently used
        self.head = Node(0, 0)  # Sentinel head
        self.tail = Node(0, 0)  # Sentinel tail
        self.head.next = self.tail
        self.tail.prev = self.head

    def get(self, key: int) -> int:
        """
        Retrieve value for a key. Mark as most recently used. O(1).

        Returns: Value if found, -1 if not found.
        """
        if key not in self.cache:
            return -1

        node = self.cache[key]
        self._move_to_end(node)  # Mark as most recently used
        return node.value

    def put(self, key: int, value: int) -> None:
        """
        Add or update a key-value pair. Mark as most recently used. O(1).

        If capacity exceeded after adding, evict the least recently used item.
        """
        if key in self.cache:
            # Update existing key
            node = self.cache[key]
            node.value = value
            self._move_to_end(node)
        else:
            # Add new key
            if len(self.cache) >= self.capacity:
                # Evict least recently used (right after head)
                self._remove_node(self.head.next)

            # Create and add new node
            node = Node(key, value)
            self.cache[key] = node
            self._add_to_end(node)

    def _move_to_end(self, node: Node) -> None:
        """Remove node from list and re-add it at the end (most recently used)."""
        self._remove_node(node)
        self._add_to_end(node)

    def _add_to_end(self, node: Node) -> None:
        """Add node to the end of the list (before tail sentinel)."""
        node.prev = self.tail.prev
        node.next = self.tail
        self.tail.prev.next = node
        self.tail.prev = node

    def _remove_node(self, node: Node) -> None:
        """Remove node from the doubly-linked list."""
        node.prev.next = node.next
        node.next.prev = node.prev
        if node.key in self.cache:
            del self.cache[node.key]


# Example usage
if __name__ == "__main__":
    lru = LRUCache(2)
    lru.put(1, 1)
    lru.put(2, 2)
    print(lru.get(1))  # 1

    lru.put(3, 3)     # Evicts key 2
    print(lru.get(2))  # -1

    lru.put(4, 4)     # Evicts key 1
    print(lru.get(1))  # -1
    print(lru.get(3))  # 3
    print(lru.get(4))  # 4