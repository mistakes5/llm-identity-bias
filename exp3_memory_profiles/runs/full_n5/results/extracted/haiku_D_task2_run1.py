from typing import Optional, Any

class Node:
    """Doubly-linked list node for LRU cache."""
    def __init__(self, key: Any, value: Any):
        self.key = key
        self.value = value
        self.prev: Optional['Node'] = None
        self.next: Optional['Node'] = None

class LRUCache:
    """LRU Cache with O(1) get and put operations.
    
    Architecture:
    - HashMap (dict): O(1) key lookups
    - Doubly-Linked List: O(1) reordering
    - Sentinel head/tail: Eliminates boundary edge cases
    """

    def __init__(self, capacity: int):
        if capacity < 1:
            raise ValueError("Capacity must be at least 1")
        
        self.capacity = capacity
        self.cache: dict[Any, Node] = {}
        
        # Sentinel nodes avoid null checks
        self.head = Node(None, None)
        self.tail = Node(None, None)
        self.head.next = self.tail
        self.tail.prev = self.head

    def get(self, key: Any) -> Optional[Any]:
        """O(1) retrieval. Marks accessed node as recently used."""
        if key not in self.cache:
            return None
        
        node = self.cache[key]
        self._move_to_end(node)  # Mark as recently used
        return node.value

    def put(self, key: Any, value: Any) -> None:
        """O(1) insertion/update. Evicts LRU item if capacity exceeded."""
        # Case 1: Key exists — update and mark as recent
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            self._move_to_end(node)
            return
        
        # Case 2: New key — add to end (most recent)
        node = Node(key, value)
        self.cache[key] = node
        self._add_to_end(node)
        
        # Case 3: Over capacity — evict LRU (head.next)
        if len(self.cache) > self.capacity:
            self._evict_lru()

    def _move_to_end(self, node: Node) -> None:
        """Remove from position and append to end."""
        self._remove_node(node)
        self._add_to_end(node)

    def _add_to_end(self, node: Node) -> None:
        """Insert before tail (end of list)."""
        node.prev = self.tail.prev
        node.next = self.tail
        self.tail.prev.next = node
        self.tail.prev = node

    def _remove_node(self, node: Node) -> None:
        """Unlink node from list."""
        node.prev.next = node.next
        node.next.prev = node.prev

    def _evict_lru(self) -> None:
        """Remove least recently used (head.next)."""
        lru_node = self.head.next
        self._remove_node(lru_node)
        del self.cache[lru_node.key]

cache = LRUCache(2)

cache.put(1, "apple")      # Cache: {1: apple}
cache.put(2, "banana")     # Cache: {1: apple, 2: banana}
print(cache.get(1))        # "apple" + moves 1 to end → Cache order: 2, 1

cache.put(3, "cherry")     # Over capacity → evicts 2 → Cache: {1: apple, 3: cherry}
print(cache.get(2))        # None (evicted)