# LRU (Least Recently Used) Cache Implementation
# Time complexity: get() and put() are both O(1)
# Space complexity: O(capacity)

class Node:
    # Node in a doubly-linked list
    # We need both pointers (prev/next) so we can remove any node in O(1) time
    def __init__(self, key, value):
        self.key = key
        self.value = value
        self.prev = None  # pointer to previous node
        self.next = None  # pointer to next node


class LRUCache:
    # An LRU cache stores recently-used data and evicts the oldest item
    # when capacity is exceeded.

    def __init__(self, capacity):
        # capacity: maximum number of items the cache can hold
        self.capacity = capacity

        # Dictionary: key -> Node
        # This gives us O(1) lookups by key
        self.cache = {}

        # Doubly-linked list to track access order
        # Most recent item is closest to HEAD
        # Least recent item is closest to TAIL
        self.head = Node(0, 0)  # dummy head node (sentinel)
        self.tail = Node(0, 0)  # dummy tail node (sentinel)

        # Connect the dummy nodes
        self.head.next = self.tail
        self.tail.prev = self.head

    def _add_to_front(self, node):
        # Add a node right after HEAD (making it the most recently used)
        # This is O(1) because we're just adjusting pointers
        node.prev = self.head
        node.next = self.head.next
        self.head.next.prev = node
        self.head.next = node

    def _remove_node(self, node):
        # Remove a node from the doubly-linked list
        # This is O(1) because we have direct pointers
        prev_node = node.prev
        next_node = node.next
        prev_node.next = next_node
        next_node.prev = prev_node

    def _move_to_front(self, node):
        # When we access a node, move it to the front (mark as recently used)
        self._remove_node(node)
        self._add_to_front(node)

    def get(self, key):
        # Return the value for a key, or -1 if not found
        # Also marks the item as recently used (move to front)
        # Time: O(1)

        if key not in self.cache:
            return -1

        # Get the node from cache
        node = self.cache[key]

        # Mark it as recently used by moving to front
        self._move_to_front(node)

        return node.value

    def put(self, key, value):
        # Add or update a key-value pair
        # If cache is full, evict the least recently used item
        # Time: O(1)

        if key in self.cache:
            # Key already exists: update value and mark as recently used
            node = self.cache[key]
            node.value = value
            self._move_to_front(node)
        else:
            # New key: create a new node
            node = Node(key, value)
            self.cache[key] = node
            self._add_to_front(node)

            # Check if we exceeded capacity
            if len(self.cache) > self.capacity:
                # Remove the least recently used item (node before TAIL)
                lru_node = self.tail.prev
                self._remove_node(lru_node)
                del self.cache[lru_node.key]


# Example usage
if __name__ == "__main__":
    lru = LRUCache(capacity=2)

    # Add items
    lru.put(1, "one")
    lru.put(2, "two")
    print(f"Get 1: {lru.get(1)}")  # Returns "one", marks 1 as recently used

    # Capacity is 2, so adding a third item evicts the least recently used (2)
    lru.put(3, "three")
    print(f"Get 2: {lru.get(2)}")  # Returns -1 (was evicted)

    # Update an existing key
    lru.put(1, "ONE")
    print(f"Get 1: {lru.get(1)}")  # Returns "ONE"

cache = LRUCache(capacity=2)

# Put and get work as expected
cache.put(1, "apple")
cache.put(2, "banana")
print(cache.get(1))  # "apple" — also marks 1 as recently used

# When adding a 3rd item to a capacity=2 cache,
# item 2 (least recently used) gets evicted
cache.put(3, "cherry")
print(cache.get(2))  # -1, because 2 was evicted