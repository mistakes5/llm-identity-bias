# ================================================================
# LRU Cache — Least Recently Used Cache
# ================================================================
#
# WHAT IS AN LRU CACHE?
# Imagine a small whiteboard that can only hold 3 sticky notes.
# When it's full and you add a new note, you erase the note
# you wrote the LONGEST TIME AGO (least recently used).
#
# HOW WE ACHIEVE O(1) SPEED:
# We combine TWO data structures:
#
#   1. A Python dictionary
#      → Lets us FIND any item by key instantly (O(1) lookup)
#
#   2. A doubly-linked list
#      → Lets us REORDER items in O(1) by just swapping pointers
#      → "Most recently used" items live near the HEAD
#      → "Least recently used" items live near the TAIL
#
# Visual layout:
#  [dummy_head] <-> [most recent] <-> [...] <-> [least recent] <-> [dummy_tail]
#
# ================================================================


# ----------------------------------------------------------------
# Part 1: The Node class — one "slot" in our linked list
# ----------------------------------------------------------------
# NOTE: A "class" is like a blueprint.
# Every Node has a key, a value, and knows its two neighbors.

class Node:
    def __init__(self, key, value):
        self.key   = key    # The label we look things up by (e.g. 1)
        self.value = value  # The actual data stored (e.g. "apple")
        self.prev  = None   # Pointer to the node to the LEFT (more recent)
        self.next  = None   # Pointer to the node to the RIGHT (less recent)


# ----------------------------------------------------------------
# Part 2: The LRUCache class
# ----------------------------------------------------------------

class LRUCache:

    def __init__(self, capacity):
        self.capacity = capacity  # Max items we can hold

        # Dictionary: key → Node object
        # This lets us jump to any node in O(1) — no searching needed!
        self.cache = {}

        # Two dummy sentinel nodes as stable bookmarks at each end.
        # They never hold real data — just make the code cleaner.
        self.head = Node(0, 0)   # Left sentinel  (MRU side)
        self.tail = Node(0, 0)   # Right sentinel (LRU side)

        # Connect them so we start with:  [head] <-> [tail]
        self.head.next = self.tail
        self.tail.prev = self.head

    # ---- Private helpers (the _ prefix means "internal use only") ----

    def _add_to_front(self, node):
        # Insert 'node' right after head — marks it as Most Recently Used
        #
        # Before:  [head] <-> [old_first] <-> ...
        # After:   [head] <-> [node] <-> [old_first] <-> ...

        node.prev = self.head           # node's left  = head
        node.next = self.head.next      # node's right = old first node

        self.head.next.prev = node      # old first node now points back to node
        self.head.next      = node      # head now points forward to node

    def _remove(self, node):
        # Unlink 'node' from its current position in the list
        #
        # Before:  [prev] <-> [node] <-> [next]
        # After:   [prev] <-> [next]

        prev_node = node.prev
        next_node = node.next

        prev_node.next = next_node   # prev skips over node → points to next
        next_node.prev = prev_node   # next skips over node → points to prev

    # ---- Public interface ----

    def get(self, key):
        # Return the value for 'key', or -1 if not in cache.
        # Also moves the item to the front (marks it as MRU).
        # Time complexity: O(1)

        if key not in self.cache:
            return -1               # Cache miss: key not found

        node = self.cache[key]      # Cache hit: grab the node instantly

        # This item was just used — move it to the MRU position
        self._remove(node)
        self._add_to_front(node)

        return node.value

    def put(self, key, value):
        # Insert or update key→value in the cache.
        # Evicts the Least Recently Used item if over capacity.
        # Time complexity: O(1)

        # --- Case 1: Key already exists — update it ---
        if key in self.cache:
            node = self.cache[key]  # Find the existing node
            node.value = value      # Update its value in-place

            # Move it to the front — it was just used
            self._remove(node)
            self._add_to_front(node)
            return                  # Done! No need to check capacity

        # --- Case 2: New key — create a fresh node ---
        new_node = Node(key, value)
        self.cache[key] = new_node   # Register in dictionary
        self._add_to_front(new_node) # Place at MRU position

        # If we're over capacity, evict the Least Recently Used item
        if len(self.cache) > self.capacity:
            lru_node = self.tail.prev   # LRU item is just before the dummy tail
            self._remove(lru_node)          # Detach from linked list
            del self.cache[lru_node.key]    # Remove from dictionary too!

    def __repr__(self):
        # Shows cache contents from Most → Least Recently Used.
        # Just print(lru) to see the state while debugging!
        items = []
        current = self.head.next       # Start just after dummy head
        while current != self.tail:    # Stop at dummy tail
            items.append(f"{current.key}:{current.value}")
            current = current.next
        return "Cache [MRU→LRU]: " + " → ".join(items)


# ================================================================
# Demo
# ================================================================

lru = LRUCache(3)

lru.put(1, "apple");   print(f"put(1)  → {lru}")
lru.put(2, "banana");  print(f"put(2)  → {lru}")
lru.put(3, "cherry");  print(f"put(3)  → {lru}")

print()

# Accessing key 1 makes it MRU — key 2 becomes the new LRU
print(f"get(1) = {lru.get(1)}   ← also moves key 1 to front")
print(f"        → {lru}")

print()

# Adding key 4 triggers eviction — key 2 is LRU, so it gets removed
lru.put(4, "date")
print(f"put(4)  → {lru}   (key 2 evicted!)")

print()

print(f"get(2) = {lru.get(2)}    ← -1 means evicted")
print(f"get(4) = {lru.get(4)}")
print(f"get(3) = {lru.get(3)}")

def put(self, key, value):
    if key in self.cache:
        # Your 4 lines here:
        # 1. Get the existing node from self.cache[key]
        # 2. Update its .value
        # 3. Remove it from its current list position
        # 4. Add it back to the front
        return

    # ... rest of the method