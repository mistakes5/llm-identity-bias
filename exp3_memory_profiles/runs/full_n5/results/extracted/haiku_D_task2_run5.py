from typing import Optional, Any


class Node:
    """Doubly-linked list node for O(1) insertion/deletion."""
    def __init__(self, key: int = 0, value: Any = 0):
        self.key = key
        self.value = value
        self.prev: Optional['Node'] = None
        self.next: Optional['Node'] = None


class LRUCache:
    """
    LRU Cache with O(1) get and put operations.

    Design:
    - HashMap (dict) for O(1) key → node lookup
    - Doubly-linked list for O(1) recency ordering  
    - Head = oldest (LRU), Tail = newest (MRU)
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache: dict[int, Node] = {}
        
        # Sentinel nodes to avoid null checks
        self.head = Node()  # Dummy head
        self.tail = Node()  # Dummy tail
        self.head.next = self.tail
        self.tail.prev = self.head

    def get(self, key: int) -> int:
        """Retrieve value and mark as most recently used. O(1)"""
        if key not in self.cache:
            return -1
        
        node = self.cache[key]
        self._move_to_tail(node)  # Mark as MRU
        return node.value

    def put(self, key: int, value: Any) -> None:
        """Add/update key-value pair, evict LRU if needed. O(1)"""
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            self._move_to_tail(node)
        else:
            if len(self.cache) >= self.capacity:
                self._evict_lru()
            
            node = Node(key, value)
            self.cache[key] = node
            self._add_to_tail(node)

    def _move_to_tail(self, node: Node) -> None:
        """Remove node from current position and add to tail (MRU)."""
        self._remove_node(node)
        self._add_to_tail(node)

    def _add_to_tail(self, node: Node) -> None:
        """Add node right before tail (most recent position)."""
        prev_node = self.tail.prev
        prev_node.next = node
        node.prev = prev_node
        node.next = self.tail
        self.tail.prev = node

    def _remove_node(self, node: Node) -> None:
        """Remove node from its current position."""
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node

    def _evict_lru(self) -> None:
        """Remove least recently used node (first after head)."""
        lru_node = self.head.next
        self._remove_node(lru_node)
        del self.cache[lru_node.key]