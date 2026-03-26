class LRUCache:
    """LRU Cache with O(1) get and put operations."""
    
    class Node:
        def __init__(self, key, value):
            self.key = key
            self.value = value
            self.prev = None
            self.next = None
    
    def __init__(self, capacity: int):
        """Initialize cache with fixed capacity."""
        if capacity < 1:
            raise ValueError("Capacity must be at least 1")
        self.capacity = capacity
        self.cache = {}  # key → Node
        
        # Sentinel nodes to simplify list operations (no edge cases)
        self.head = self.Node(None, None)
        self.tail = self.Node(None, None)
        self.head.next = self.tail
        self.tail.prev = self.head
    
    def get(self, key: int) -> int:
        """Get value by key. Raises KeyError if not found. Marks as recently used."""
        if key not in self.cache:
            raise KeyError(f"Key {key} not found")
        
        node = self.cache[key]
        self._move_to_tail(node)  # Mark as recently used
        return node.value
    
    def put(self, key: int, value: int) -> None:
        """Put key-value pair. If key exists, update value. If at capacity, evict LRU."""
        if key in self.cache:
            # Update existing node
            node = self.cache[key]
            node.value = value
            self._move_to_tail(node)
        else:
            # Add new node
            if len(self.cache) >= self.capacity:
                self._evict_lru()
            
            node = self.Node(key, value)
            self.cache[key] = node
            self._add_to_tail(node)
    
    def _move_to_tail(self, node: 'LRUCache.Node') -> None:
        """Remove node and re-insert at tail (most recently used)."""
        self._remove_node(node)
        self._add_to_tail(node)
    
    def _remove_node(self, node: 'LRUCache.Node') -> None:
        """Remove node from doubly-linked list."""
        node.prev.next = node.next
        node.next.prev = node.prev
    
    def _add_to_tail(self, node: 'LRUCache.Node') -> None:
        """Insert node before tail (most recently used position)."""
        node.prev = self.tail.prev
        node.next = self.tail
        self.tail.prev.next = node
        self.tail.prev = node
    
    def _evict_lru(self) -> None:
        """Remove least recently used item (head of list)."""
        lru_node = self.head.next
        self._remove_node(lru_node)
        del self.cache[lru_node.key]

# Create cache with capacity 3
cache = LRUCache(3)

cache.put(1, "a")
cache.put(2, "b")
cache.put(3, "c")

print(cache.get(1))  # "a" → moves (1) to recently used

cache.put(4, "d")   # Evicts (2) because it's least recently used
# Order now: 1 → 3 → 4

print(cache.get(3))  # "c" → moves (3) to recently used
# Order: 1 → 4 → 3

try:
    cache.get(2)     # KeyError: 2 was evicted
except KeyError as e:
    print(f"Error: {e}")