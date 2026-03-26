# ============================================================
# LRU (Least Recently Used) Cache — Python Implementation
# ============================================================
#
# WHAT IS AN LRU CACHE?
#   A fixed-size storage that remembers ORDER of use.
#   When full, it throws out whatever was used LEAST RECENTLY.
#
# HOW IT ACHIEVES O(1) FOR BOTH OPERATIONS:
#   dictionary  → O(1) "is this key in the cache?"
#   linked list → O(1) "move this item to most-recently-used"
#
#   The trick: the dictionary maps keys to LIST NODES,
#   not just values. That's what makes both ops O(1).
#
#   List layout (most-recent ← left,  least-recent → right):
#
#       head <──> [newest] <──> [B] <──> [oldest] <──> tail
#       (dummy)                                   (dummy)
# ============================================================


# ── PART 1: Node ────────────────────────────────────────────
# A "class" is a blueprint for creating objects.
# Every Node you create gets its own copy of these 4 variables.

class Node:
    """One item inside the doubly-linked list."""

    def __init__(self, key, value):
        # __init__ runs automatically when you write: Node(key, value)
        # "self" refers to the specific object being created right now
        self.key   = key    # the lookup key  (e.g. 1, "username")
        self.value = value  # the data stored at that key
        self.prev  = None   # arrow pointing LEFT  (toward head)
        self.next  = None   # arrow pointing RIGHT (toward tail)


# ── PART 2: LRUCache ────────────────────────────────────────

class LRUCache:
    """Fixed-capacity cache. O(1) get and put."""

    def __init__(self, capacity):
        self.capacity = capacity   # max number of real items
        self.cache    = {}         # { key: Node }  — O(1) lookup

        # Two "dummy" nodes anchor the ends; real data lives between them
        self.head = Node(0, 0)     # left sentinel  (most-recent end)
        self.tail = Node(0, 0)     # right sentinel (least-recent end)

        self.head.next = self.tail   # connect them to form an empty list
        self.tail.prev = self.head


    # ── Private helpers ─────────────────────────────────────
    # The "_" prefix is a Python convention: "internal use only"

    def _remove_node(self, node):
        """Snip a node out of the list (does NOT delete it). O(1)."""
        #  Before:  ... prev <──> node <──> nxt ...
        #  After:   ... prev <──> nxt ...
        prev = node.prev
        nxt  = node.next
        prev.next = nxt
        nxt.prev  = prev

    def _insert_after_head(self, node):
        """Place a node right after the dummy head (= mark as most-recent). O(1)."""
        #  Before:  head <──> first ...
        #  After:   head <──> node <──> first ...
        node.prev           = self.head
        node.next           = self.head.next
        self.head.next.prev = node
        self.head.next      = node


    # ── Public API ──────────────────────────────────────────

    def get(self, key):
        """Return the value for key, or -1 if it isn't cached."""
        if key not in self.cache:
            return -1

        node = self.cache[key]

        # Using a key makes it "most recently used" — move it to front
        self._remove_node(node)
        self._insert_after_head(node)

        return node.value


    def put(self, key, value):
        """Store key → value. Evicts the LRU item if we're at capacity."""

        # Case 1: key already exists → just update it and refresh position
        if key in self.cache:
            node = self.cache[key]
            node.value = value
            self._remove_node(node)
            self._insert_after_head(node)
            return

        # Case 2: brand-new key
        new_node = Node(key, value)

        # ╔══════════════════════════════════════════════════════════╗
        # ║  YOUR TURN!                                              ║
        # ║                                                          ║
        # ║  Add ~6 lines here to handle a brand-new key:           ║
        # ║                                                          ║
        # ║  A) If the cache is AT capacity, evict the LRU item.    ║
        # ║     • self.tail.prev  is always the least-recent node   ║
        # ║     • Call self._remove_node(lru)  to unlink it         ║
        # ║     • del self.cache[lru.key]  so the dict stays clean  ║
        # ║                                                          ║
        # ║  B) Insert new_node at the front of the list:           ║
        # ║     • self._insert_after_head(new_node)                 ║
        # ║                                                          ║
        # ║  C) Register it in the dictionary:                       ║
        # ║     • self.cache[key] = new_node                         ║
        # ║                                                          ║
        # ║  Hint: len(self.cache) tells you how many items          ║
        # ║        are currently stored.                             ║
        # ╚══════════════════════════════════════════════════════════╝
        pass   # ← delete this and write your code above


# ── Smoke test ──────────────────────────────────────────────
# Run:  python lru_cache.py
# You should see PASS on every line once put() is complete.

if __name__ == "__main__":
    cache = LRUCache(capacity=3)

    cache.put(1, "one")
    cache.put(2, "two")
    cache.put(3, "three")

    cache.get(1)          # access key 1 → order is now: 1, 3, 2  (2 is LRU)

    cache.put(4, "four")  # full! key 2 gets evicted

    r = cache.get(2)
    print("get(2):", r, "←", "PASS" if r == -1     else "FAIL (should be -1, evicted)")

    r = cache.get(3)
    print("get(3):", r, "←", "PASS" if r == "three" else "FAIL (should be 'three')")

    r = cache.get(4)
    print("get(4):", r, "←", "PASS" if r == "four"  else "FAIL (should be 'four')")

    cache.put(1, "ONE")   # update an existing key
    r = cache.get(1)
    print("get(1):", r, "←", "PASS" if r == "ONE"   else "FAIL (should be 'ONE')")