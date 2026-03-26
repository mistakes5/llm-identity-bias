class Node:
    """Doubly-linked list node for maintaining access order."""
    def __init__(self, key: int = 0, value: int = 0):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class LRUCache:
    """
    LRU Cache with O(1) get and put operations.
    
    Data Structure:
    - HashMap (dict): O(1) key → Node lookup
    - Doubly-linked list: O(1) insertion/deletion and access ordering
    
    Invariants:
    - Most recently used (MRU) item is right before tail
    - Least recently used (LRU) item is right after head
    """

    def __init__(self, capacity: int):
        if capacity <= 0:
            raise ValueError("Capacity must be positive")
        
        self.capacity = capacity
        self.cache = {}  # Maps key → Node
        
        # Sentinel nodes avoid null checks and simplify edge cases
        # head → [LRU] ... [MRU] → tail
        self.head = Node()
        self.tail = Node()
        self.head.next = self.tail
        self.tail.prev = self.head

    def get(self, key: int) -> int:
        """
        Get value by key. Marks item as most recently used.
        Time: O(1)
        """
        if key not in self.cache:
            return -1
        
        node = self.cache[key]
        self._move_to_end(node)
        return node.value

    def put(self, key: int, value: int) -> None:
        """
        Put key-value pair. Evicts LRU item if at capacity.
        Time: O(1)
        """
        if key in self.cache:
            # Update existing and mark as MRU
            node = self.cache[key]
            node.value = value
            self._move_to_end(node)
        else:
            # Add new item
            if len(self.cache) >= self.capacity:
                # Evict LRU (right after head)
                lru_node = self.head.next
                self._remove_node(lru_node)
                del self.cache[lru_node.key]
            
            # Create new node and add to MRU position
            new_node = Node(key, value)
            self.cache[key] = new_node
            self._add_to_end(new_node)

    def _move_to_end(self, node: Node) -> None:
        """Move node to MRU position (end of list)."""
        self._remove_node(node)
        self._add_to_end(node)

    def _remove_node(self, node: Node) -> None:
        """Remove node from list (pointer updates only)."""
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node

    def _add_to_end(self, node: Node) -> None:
        """Add node right before tail (MRU position)."""
        prev_node = self.tail.prev
        prev_node.next = node
        node.prev = prev_node
        node.next = self.tail
        self.tail.prev = node

cache = LRUCache(capacity=2)

cache.put(1, 100)      # {1: 100}
cache.put(2, 200)      # {1: 100, 2: 200}
print(cache.get(1))    # 100 (marks 1 as MRU)
                       # Order now: 2 (LRU), 1 (MRU)

cache.put(3, 300)      # Capacity exceeded → evict key 2 (LRU)
                       # {1: 100, 3: 300}

print(cache.get(2))    # -1 (was evicted)
print(cache.get(1))    # 100