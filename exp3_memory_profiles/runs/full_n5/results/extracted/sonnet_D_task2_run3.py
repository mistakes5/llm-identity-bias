"""
LRU Cache — O(1) get and put via HashMap + Doubly Linked List.

Structure:
    sentinel_head <-> [MRU] <-> ... <-> [LRU] <-> sentinel_tail
    dict: key -> Node
"""

from __future__ import annotations
from typing import Optional


class Node:
    __slots__ = ("key", "val", "prev", "next")

    def __init__(self, key: int = 0, val: int = 0) -> None:
        self.key  = key
        self.val  = val
        self.prev: Optional[Node] = None
        self.next: Optional[Node] = None


class LRUCache:
    def __init__(self, capacity: int) -> None:
        if capacity < 1:
            raise ValueError(f"capacity must be >= 1, got {capacity}")

        self.capacity = capacity
        self._map: dict[int, Node] = {}

        # Sentinel nodes — eliminates all edge cases (empty list, head/tail)
        self._head = Node()   # MRU side
        self._tail = Node()   # LRU side
        self._head.next = self._tail
        self._tail.prev = self._head

    def get(self, key: int) -> int:
        node = self._map.get(key)
        if node is None:
            return -1
        self._move_to_front(node)
        return node.val

    def put(self, key: int, value: int) -> None:
        node = self._map.get(key)
        if node:
            node.val = value
            self._move_to_front(node)
        else:
            node = Node(key, value)
            self._map[key] = node
            self._insert_at_front(node)
            if len(self._map) > self.capacity:
                self._evict_lru()

    # ── private helpers ─────────────────────────────────────────────────

    def _remove(self, node: Node) -> None:
        node.prev.next = node.next          # bridge over node
        node.next.prev = node.prev

    def _insert_at_front(self, node: Node) -> None:
        node.prev = self._head
        node.next = self._head.next
        self._head.next.prev = node
        self._head.next = node

    def _move_to_front(self, node: Node) -> None:
        self._remove(node)
        self._insert_at_front(node)

    def _evict_lru(self) -> None:
        lru = self._tail.prev               # node just left of sentinel
        self._remove(lru)
        del self._map[lru.key]

    def __len__(self) -> int:
        return len(self._map)

    def __repr__(self) -> str:
        items, cur = [], self._head.next
        while cur is not self._tail:
            items.append(f"{cur.key}:{cur.val}")
            cur = cur.next
        return f"LRUCache([{' -> '.join(items)}], cap={self.capacity})"