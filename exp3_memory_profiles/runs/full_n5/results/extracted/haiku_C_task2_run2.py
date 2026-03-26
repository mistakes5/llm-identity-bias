from typing import Any, Optional

class Node:
    """Doubly linked list node for tracking usage order."""
    def __init__(self, key: Any, value: Any):
        self.key = key
        self.value = value
        self.prev: Optional['Node'] = None
        self.next: Optional['Node'] = None


class LRUCache:
    """
    LRU (Least Recently Used) Cache with O(1) get and put operations.
    
    - Uses a hash map for O(1) key lookup
    - Uses a doubly linked list to track access order
    - Most recently used items move to the end
    - Least recently used items are evicted from the front when capacity is exceeded
    """
    
    def __init__(self, capacity: int):
        """Initialize cache with fixed capacity."""
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        
        self.capacity = capacity
        self.cache: dict[Any, Node] = {}  # key -> Node mapping
        
        # Dummy head and tail nodes simplify edge case handling
        self.head = Node(None, None)  # Points to least recently used
        self.tail = Node(None, None)  # Points to most recently used
        self.head.next = self.tail
        self.tail.prev = self.head
    
    def get(self, key: Any) -> Optional[Any]:
        """
        Retrieve value by key. O(1) time.
        Marks the item as recently used.
        """
        if key not in self.cache:
            return None
        
        node = self.cache[key]
        self._move_to_end(node)  # Mark as recently used
        return node.value
    
    def put(self, key: Any, value: Any) -> None:
        """
        Add or update a key-value pair. O(1) time.
        If capacity is exceeded, evicts the least recently used item.
        """
        # If key exists, update its value and mark as recently used
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            self._move_to_end(node)
            return
        
        # New key: check capacity
        if len(self.cache) >= self.capacity:
            self._evict_lru()
        
        # Create new node and add to end (most recently used position)
        new_node = Node(key, value)
        self.cache[key] = new_node
        self._add_to_end(new_node)
    
    def _move_to_end(self, node: Node) -> None:
        """Remove node from its current position and move to end."""
        self._remove_node(node)
        self._add_to_end(node)
    
    def _add_to_end(self, node: Node) -> None:
        """Add node right before tail (most recently used position)."""
        node.prev = self.tail.prev
        node.next = self.tail
        self.tail.prev.next = node
        self.tail.prev = node
    
    def _remove_node(self, node: Node) -> None:
        """Remove node from the linked list."""
        node.prev.next = node.next
        node.next.prev = node.prev
    
    def _evict_lru(self) -> None:
        """Remove the least recently used item (right after head)."""
        lru_node = self.head.next
        self._remove_node(lru_node)
        del self.cache[lru_node.key]

# Create cache with capacity 2
cache = LRUCache(capacity=2)

cache.put(1, "a")
cache.put(2, "b")
print(cache.get(1))  # Returns "a", marks 1 as recently used

cache.put(3, "c")  # Capacity exceeded! Evicts key 2 (least recently used)
print(cache.get(2))  # Returns None (was evicted)

cache.put(1, "a_updated")  # Update existing key
print(cache.get(1))  # Returns "a_updated"