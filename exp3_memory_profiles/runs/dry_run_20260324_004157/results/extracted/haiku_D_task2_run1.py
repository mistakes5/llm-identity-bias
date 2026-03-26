class Node:
    """Doubly-linked list node storing cache entry."""
    def __init__(self, key: int, value: int):
        self.key = key
        self.value = value
        self.prev: Node | None = None
        self.next: Node | None = None


class LRUCache:
    """
    LRU Cache with O(1) get and put operations.
    
    Uses:
    - Hash map for O(1) key lookup
    - Doubly-linked list for O(1) node removal and reordering
    
    List invariant:
    - Head (left) = most recently used
    - Tail (right) = least recently used (first to evict)
    """
    
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache: dict[int, Node] = {}  # key -> Node
        
        # Sentinel nodes to avoid null checks
        self.head = Node(0, 0)
        self.tail = Node(0, 0)
        self.head.next = self.tail
        self.tail.prev = self.head
    
    def get(self, key: int) -> int:
        """Get value and mark as recently used. O(1)."""
        if key not in self.cache:
            return -1
        
        node = self.cache[key]
        self._move_to_head(node)  # Mark as recently used
        return node.value
    
    def put(self, key: int, value: int) -> None:
        """Put key-value pair, evicting LRU if at capacity. O(1)."""
        if key in self.cache:
            # Update existing: modify value and move to head
            node = self.cache[key]
            node.value = value
            self._move_to_head(node)
        else:
            # New entry
            if len(self.cache) >= self.capacity:
                # Evict least recently used (node before tail)
                self._remove_node(self.tail.prev)
            
            # Add new node to head
            node = Node(key, value)
            self.cache[key] = node
            self._add_to_head(node)
    
    def _add_to_head(self, node: Node) -> None:
        """Insert node right after head. O(1)."""
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node
    
    def _remove_node(self, node: Node) -> None:
        """Unlink node from list and cache. O(1)."""
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node
        del self.cache[node.key]
    
    def _move_to_head(self, node: Node) -> None:
        """Move node to head (most recently used). O(1)."""
        self._remove_node(node)
        self._add_to_head(node)

cache = LRUCache(capacity=2)

cache.put(1, 1)
cache.put(2, 2)
print(cache.get(1))  # 1 (1 is now most recently used)

cache.put(3, 3)  # Evicts 2 (least recently used)
print(cache.get(2))  # -1 (evicted)

cache.put(2, 2)
cache.put(4, 4)  # Evicts 1 (least recently used)
print(cache.get(1))  # -1 (evicted)
print(cache.get(3))  # 3 (still in cache)
print(cache.get(4))  # 4 (still in cache)