from typing import Generic, TypeVar, Optional

T = TypeVar('T')


class Node(Generic[T]):
    """Doubly-linked list node for maintaining insertion order."""
    def __init__(self, key: str, value: T):
        self.key = key
        self.value = value
        self.prev: Optional['Node[T]'] = None
        self.next: Optional['Node[T]'] = None


class LRUCache(Generic[T]):
    """
    Least Recently Used (LRU) Cache with O(1) get and put operations.

    Architecture:
    - HashMap: dict[key → Node] for O(1) lookups
    - Doubly-Linked List: tracks access order (LRU at head, MRU at tail)
    
    Time Complexity: O(1) for both get() and put()
    Space Complexity: O(capacity)
    """

    def __init__(self, capacity: int):
        """Initialize cache with fixed capacity."""
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        
        self.capacity = capacity
        self.cache: dict[str, Node[T]] = {}
        
        # Sentinel nodes to avoid None checks
        self.head = Node("", None)
        self.tail = Node("", None)
        self.head.next = self.tail
        self.tail.prev = self.head

    def get(self, key: str) -> Optional[T]:
        """
        Get value from cache. O(1)
        
        Also marks this item as most recently used.
        """
        if key not in self.cache:
            return None
        
        node = self.cache[key]
        self._move_to_tail(node)
        return node.value

    def put(self, key: str, value: T) -> None:
        """
        Insert or update a key-value pair. O(1)
        
        If capacity exceeded, evicts the least recently used item.
        """
        # Case 1: Key exists - update value and mark as recently used
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            self._move_to_tail(node)
            return
        
        # Case 2: New key
        if len(self.cache) >= self.capacity:
            self._evict_lru()
        
        new_node = Node(key, value)
        self.cache[key] = new_node
        self._add_to_tail(new_node)

    def _move_to_tail(self, node: Node[T]) -> None:
        """Move a node to tail (mark as most recently used)."""
        self._remove_node(node)
        self._add_to_tail(node)

    def _add_to_tail(self, node: Node[T]) -> None:
        """Add node right before tail sentinel."""
        prev_node = self.tail.prev
        prev_node.next = node
        node.prev = prev_node
        node.next = self.tail
        self.tail.prev = node

    def _remove_node(self, node: Node[T]) -> None:
        """Remove node from linked list."""
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node

    def _evict_lru(self) -> None:
        """Remove least recently used item (head.next)."""
        lru_node = self.head.next
        self._remove_node(lru_node)
        del self.cache[lru_node.key]

    def __len__(self) -> int:
        return len(self.cache)

# Create cache with capacity 3
cache = LRUCache(3)

cache.put("a", 1)
cache.put("b", 2)
cache.put("c", 3)
print(cache.get("a"))  # Returns 1, marks "a" as recently used

cache.put("d", 4)  # Capacity exceeded, evicts "b" (least recently used)

print(cache.get("b"))  # Returns None (was evicted)
print(cache.get("a"))  # Returns 1
print(cache.get("c"))  # Returns 3
print(cache.get("d"))  # Returns 4

def test_lru_cache():
    # Test 1: Basic operations
    cache = LRUCache(2)
    cache.put("a", 1)
    assert cache.get("a") == 1
    cache.put("b", 2)
    cache.put("c", 3)  # Evicts "a"
    assert cache.get("a") is None
    
    # Test 2: get() marks as recently used
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.get("a")  # Access "a"
    cache.put("c", 3)  # Evicts "b" not "a"
    assert cache.get("a") == 1
    assert cache.get("b") is None
    
    # Test 3: Update existing key
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("a", 10)  # Update
    assert cache.get("a") == 10
    assert len(cache) == 1
    
    print("✓ All tests pass!")