class Node:
    """Doubly linked list node for LRU cache."""
    def __init__(self, key: int = 0, value: int = 0):
        self.key = key
        self.value = value
        self.prev: 'Node' | None = None
        self.next: 'Node' | None = None


class LRUCache:
    """
    LRU Cache with O(1) get and put operations.
    
    Design:
    - Hash map (dict) for O(1) key lookups
    - Doubly linked list to track access order
    - Most recently used items at the front (head)
    - Least recently used items at the back (tail)
    """
    
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache: dict[int, Node] = {}
        
        # Sentinel nodes: dummy head and tail for easier edge case handling
        self.head = Node()
        self.tail = Node()
        self.head.next = self.tail
        self.tail.prev = self.head
    
    def get(self, key: int) -> int:
        """
        Get value by key. Mark as recently used. O(1) time.
        Returns -1 if key doesn't exist.
        """
        if key not in self.cache:
            return -1
        
        node = self.cache[key]
        self._move_to_front(node)  # Mark as recently used
        return node.value
    
    def put(self, key: int, value: int) -> None:
        """
        Insert or update key-value pair. O(1) time.
        If at capacity and inserting new key, evict least recently used.
        """
        if key in self.cache:
            # Key exists: update value and mark as recently used
            node = self.cache[key]
            node.value = value
            self._move_to_front(node)
        else:
            # Key doesn't exist: create new node
            if len(self.cache) == self.capacity:
                # At capacity: evict least recently used (rightmost before tail)
                self._remove_node(self.tail.prev)
            
            # Add new node to front (most recently used)
            new_node = Node(key, value)
            self.cache[key] = new_node
            self._add_to_front(new_node)
    
    def _add_to_front(self, node: Node) -> None:
        """Add node right after head (most recently used position)."""
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node
    
    def _remove_node(self, node: Node) -> None:
        """Remove node from linked list and cache."""
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node
        del self.cache[node.key]
    
    def _move_to_front(self, node: Node) -> None:
        """Move node to front (mark as recently used)."""
        self._remove_node(node)
        self._add_to_front(node)


# ============================================================================
# Test Cases
# ============================================================================

def test_lru_cache():
    """Test LRU cache functionality."""
    
    # Test 1: Basic get and put
    cache = LRUCache(2)
    cache.put(1, 1)
    cache.put(2, 2)
    assert cache.get(1) == 1
    assert cache.get(2) == 2
    print("✓ Test 1: Basic get and put")
    
    # Test 2: Eviction of least recently used
    cache = LRUCache(2)
    cache.put(1, 1)
    cache.put(2, 2)
    cache.put(3, 3)  # Should evict key 1 (least recently used)
    assert cache.get(1) == -1  # 1 was evicted
    assert cache.get(3) == 3
    print("✓ Test 2: Eviction of least recently used")
    
    # Test 3: Access updates recency
    cache = LRUCache(2)
    cache.put(1, 1)
    cache.put(2, 2)
    cache.get(1)  # Access 1, making it recently used
    cache.put(3, 3)  # Should evict key 2 (now least recently used)
    assert cache.get(1) == 1
    assert cache.get(2) == -1  # 2 was evicted
    assert cache.get(3) == 3
    print("✓ Test 3: Access updates recency")
    
    # Test 4: Update existing key
    cache = LRUCache(2)
    cache.put(1, 1)
    cache.put(1, 100)  # Update key 1
    assert cache.get(1) == 100
    print("✓ Test 4: Update existing key")
    
    # Test 5: Capacity of 1
    cache = LRUCache(1)
    cache.put(1, 1)
    cache.put(2, 2)  # Should evict key 1
    assert cache.get(1) == -1
    assert cache.get(2) == 2
    print("✓ Test 5: Capacity of 1")
    
    # Test 6: Complex access pattern
    cache = LRUCache(3)
    cache.put(1, 1)
    cache.put(2, 2)
    cache.put(3, 3)
    cache.get(1)  # [1, 3, 2] (1 accessed, 2 is least recent)
    cache.put(4, 4)  # Evicts 2
    assert cache.get(2) == -1
    cache.get(3)  # [3, 1, 4] (3 accessed, 4 is least recent)
    cache.put(5, 5)  # Evicts 4
    assert cache.get(4) == -1
    assert cache.get(1) == 1
    assert cache.get(3) == 3
    assert cache.get(5) == 5
    print("✓ Test 6: Complex access pattern")
    
    print("\n✅ All tests passed!")


if __name__ == "__main__":
    test_lru_cache()

cache = LRUCache(2)

cache.put(1, 1)    # Cache: {1: 1}
cache.put(2, 2)    # Cache: {1: 1, 2: 2}
cache.get(1)       # Returns 1, marks 1 as recently used
cache.put(3, 3)    # At capacity, evicts 2 (least recent), adds 3
                   # Cache: {1: 1, 3: 3}
cache.get(2)       # Returns -1 (2 was evicted)