class Node:
    """Doubly linked list node for tracking usage order."""
    def __init__(self, key=0, value=0):
        self.key = key
        self.value = value
        self.prev = None
        self.next = None


class LRUCache:
    """
    LRU Cache with O(1) get and put operations.

    Data Structures:
    - Dictionary (hash map): O(1) key lookup and deletion
    - Doubly Linked List: O(1) node removal and insertion

    Design:
    - Head → [LRU ... MRU] → Tail
    - Accessing/updating a key moves it to the tail (most recent)
    - When capacity exceeded, remove the head.next (least recent)
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.cache = {}  # key -> Node mapping

        # Sentinel nodes eliminate boundary checks
        self.head = Node()  # dummy node before LRU
        self.tail = Node()  # dummy node after MRU
        self.head.next = self.tail
        self.tail.prev = self.head

    def _remove(self, node: Node) -> None:
        """Remove node from list - O(1)"""
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node

    def _add_to_tail(self, node: Node) -> None:
        """Add node right before tail (mark as most recently used) - O(1)"""
        prev_node = self.tail.prev
        prev_node.next = node
        node.prev = prev_node
        node.next = self.tail
        self.tail.prev = node

    def get(self, key: int) -> int:
        """
        Get value and mark as recently used.
        Time: O(1)
        - Dict lookup: O(1)
        - Node removal: O(1)
        - Node insertion: O(1)
        """
        if key not in self.cache:
            return -1

        node = self.cache[key]
        # Move to tail (mark as most recently used)
        self._remove(node)
        self._add_to_tail(node)
        return node.value

    def put(self, key: int, value: int) -> None:
        """
        Insert or update key-value pair.
        Evict LRU item if capacity exceeded.
        Time: O(1)
        """
        if key in self.cache:
            # Update existing key
            node = self.cache[key]
            node.value = value
            self._remove(node)
            self._add_to_tail(node)
        else:
            # Insert new key
            if len(self.cache) >= self.capacity:
                # Evict LRU (head.next)
                lru_node = self.head.next
                self._remove(lru_node)
                del self.cache[lru_node.key]

            # Add new node
            new_node = Node(key, value)
            self.cache[key] = new_node
            self._add_to_tail(new_node)


# Test cases
if __name__ == "__main__":
    cache = LRUCache(2)
    
    # Test 1: Basic operations
    cache.put(1, 1)
    cache.put(2, 2)
    assert cache.get(1) == 1  # Returns 1
    
    # Test 2: Eviction
    cache.put(3, 3)  # Evicts key 2 (LRU)
    assert cache.get(2) == -1  # Key 2 no longer exists
    assert cache.get(1) == 1
    assert cache.get(3) == 3
    
    # Test 3: Update moves to recent
    cache.put(1, 10)  # Update and mark as recently used
    cache.put(4, 4)   # Evicts key 3 (not 1)
    assert cache.get(3) == -1  # 3 was evicted
    assert cache.get(1) == 10
    assert cache.get(4) == 4
    
    print("✓ All tests passed!")