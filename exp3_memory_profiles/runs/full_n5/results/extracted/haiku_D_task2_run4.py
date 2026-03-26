class Node:
    """Doubly linked list node for the LRU cache."""
    def __init__(self, key: int, value: int):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class LRUCache:
    """O(1) LRU cache with fixed capacity."""
    
    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        self.capacity = capacity
        self.cache = {}  # key -> Node mapping
        
        # Sentinel nodes: dummy head and tail for easier list manipulation
        self.head = Node(0, 0)  # Most recently used end
        self.tail = Node(0, 0)  # Least recently used end
        self.head.next = self.tail
        self.tail.prev = self.head
    
    def get(self, key: int) -> int:
        """
        Get value by key and mark as recently used.
        Returns -1 if key not found.
        Time: O(1)
        """
        if key not in self.cache:
            return -1
        
        node = self.cache[key]
        self._move_to_head(node)  # Mark as recently used
        return node.value
    
    def put(self, key: int, value: int) -> None:
        """
        Insert or update a key-value pair.
        Evicts the LRU item if capacity is exceeded.
        Time: O(1)
        """
        if key in self.cache:
            # Update existing node
            node = self.cache[key]
            node.value = value
            self._move_to_head(node)
        else:
            # Add new node
            if len(self.cache) >= self.capacity:
                self._evict_lru()
            
            node = Node(key, value)
            self.cache[key] = node
            self._add_to_head(node)
    
    def _move_to_head(self, node: Node) -> None:
        """Move a node to the head (most recently used position)."""
        self._remove_node(node)
        self._add_to_head(node)
    
    def _add_to_head(self, node: Node) -> None:
        """Add a node right after the head sentinel."""
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node
    
    def _remove_node(self, node: Node) -> None:
        """Remove a node from its current position."""
        node.prev.next = node.next
        node.next.prev = node.prev
    
    def _evict_lru(self) -> None:
        """Remove the least recently used (tail) node."""
        lru_node = self.tail.prev
        self._remove_node(lru_node)
        del self.cache[lru_node.key]


# Example usage and test cases
if __name__ == "__main__":
    cache = LRUCache(capacity=2)
    
    # Test 1: Basic put and get
    cache.put(1, 1)
    cache.put(2, 2)
    assert cache.get(1) == 1  # Access 1, making it recently used
    print("✓ Test 1: Basic operations")
    
    # Test 2: Eviction on overflow
    cache.put(3, 3)  # Evicts key 2 (least recently used)
    assert cache.get(2) == -1  # 2 was evicted
    assert cache.get(3) == 3
    print("✓ Test 2: LRU eviction")
    
    # Test 3: Update existing key
    cache.put(1, 10)  # Update 1's value and mark as recently used
    cache.put(4, 4)   # Evicts key 3 (least recently used)
    assert cache.get(1) == 10
    assert cache.get(3) == -1
    print("✓ Test 3: Update and eviction")
    
    # Test 4: Multiple evictions
    cache = LRUCache(3)
    cache.put(1, 1)
    cache.put(2, 2)
    cache.put(3, 3)
    cache.get(1)      # 1 is now most recently used
    cache.put(4, 4)   # Evicts 2
    cache.put(5, 5)   # Evicts 3
    assert cache.get(1) == 1
    assert cache.get(4) == 4
    assert cache.get(5) == 5
    assert cache.get(2) == -1
    assert cache.get(3) == -1
    print("✓ Test 4: Multiple evictions")
    
    print("\nAll tests passed! ✓")