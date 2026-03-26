from typing import Optional

class Node:
    """Doubly-linked list node for LRU cache."""
    def __init__(self, key: int, value: int):
        self.key = key
        self.value = value
        self.prev: Optional[Node] = None
        self.next: Optional[Node] = None


class LRUCache:
    """
    LRU (Least Recently Used) cache with O(1) get and put operations.
    
    Maintains a fixed-size cache. When capacity is exceeded, the least
    recently used item is evicted.
    """
    
    def __init__(self, capacity: int):
        """
        Initialize LRU cache.
        
        Args:
            capacity: Maximum number of items the cache can hold
        """
        if capacity < 1:
            raise ValueError("Capacity must be at least 1")
        
        self.capacity = capacity
        self.cache: dict[int, Node] = {}  # key -> Node mapping
        
        # Sentinel nodes to avoid edge case handling
        self.head = Node(0, 0)  # Least recently used
        self.tail = Node(0, 0)  # Most recently used
        self.head.next = self.tail
        self.tail.prev = self.head
    
    def get(self, key: int) -> int:
        """
        Get value by key and mark it as recently used.
        
        Args:
            key: The key to look up
            
        Returns:
            The value associated with the key, or -1 if not found
            
        Time Complexity: O(1)
        """
        if key not in self.cache:
            return -1
        
        node = self.cache[key]
        self._move_to_tail(node)  # Mark as most recently used
        return node.value
    
    def put(self, key: int, value: int) -> None:
        """
        Add or update a key-value pair, marking it as recently used.
        
        If cache is at capacity and key is new, evicts the least recently used item.
        
        Args:
            key: The key to add/update
            value: The value to associate with the key
            
        Time Complexity: O(1)
        """
        if key in self.cache:
            # Update existing node
            node = self.cache[key]
            node.value = value
            self._move_to_tail(node)
        else:
            # Add new node
            if len(self.cache) >= self.capacity:
                self._evict_head()
            
            new_node = Node(key, value)
            self.cache[key] = new_node
            self._add_to_tail(new_node)
    
    def _move_to_tail(self, node: Node) -> None:
        """Move node to tail (most recently used position). O(1)."""
        self._remove_node(node)
        self._add_to_tail(node)
    
    def _remove_node(self, node: Node) -> None:
        """Remove node from linked list. O(1)."""
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node
    
    def _add_to_tail(self, node: Node) -> None:
        """Add node to tail (most recently used position). O(1)."""
        prev_node = self.tail.prev
        prev_node.next = node
        node.prev = prev_node
        node.next = self.tail
        self.tail.prev = node
    
    def _evict_head(self) -> None:
        """Remove least recently used item (head's next). O(1)."""
        lru_node = self.head.next
        self._remove_node(lru_node)
        del self.cache[lru_node.key]


# Test the implementation
if __name__ == "__main__":
    # Test 1: Basic get/put
    cache = LRUCache(2)
    cache.put(1, 1)
    cache.put(2, 2)
    assert cache.get(1) == 1, "Should get value 1"
    
    # Test 2: Eviction (capacity is 2)
    cache.put(3, 3)  # Evicts key 2
    assert cache.get(2) == -1, "Key 2 should be evicted"
    
    # Test 3: Access updates recency
    cache.put(4, 4)  # Evicts key 1 (was least recently used)
    assert cache.get(1) == -1, "Key 1 should be evicted"
    assert cache.get(3) == 3, "Key 3 should still exist"
    assert cache.get(4) == 4, "Key 4 should exist"
    
    # Test 4: Updating existing key doesn't evict
    cache.put(3, 30)  # Update key 3
    assert cache.get(3) == 30, "Key 3 value should be updated"
    assert cache.get(4) == 4, "Key 4 should still exist"
    
    print("✓ All tests passed!")

from collections import OrderedDict

class LRUCache:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = OrderedDict()
    
    def get(self, key: int) -> int:
        if key not in self.cache:
            return -1
        self.cache.move_to_end(key)  # Mark as recently used
        return self.cache[key]
    
    def put(self, key: int, value: int) -> None:
        if key in self.cache:
            self.cache[key] = value
            self.cache.move_to_end(key)
        else:
            if len(self.cache) >= self.capacity:
                self.cache.popitem(last=False)  # Remove oldest (first)
            self.cache[key] = value