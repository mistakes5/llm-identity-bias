#!/usr/bin/env python3
"""
tasks.py — A command-line task manager with persistent JSON storage.

Usage:
  python tasks.py add "Buy groceries" --priority high --tags personal,errands
  python tasks.py list
  python tasks.py list --status all --tag work --priority high
  python tasks.py done abc123
  python tasks.py undo abc123
  python tasks.py delete abc123
  python tasks.py show abc123
"""

import argparse, json, os, sys, uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

DATA_DIR  = Path(os.environ.get("TASKS_DIR", Path.home() / ".local" / "share" / "tasks"))
DATA_FILE = DATA_DIR / "tasks.json"

_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None

class C:
    RESET  = "\033[0m"  if _USE_COLOR else ""
    BOLD   = "\033[1m"  if _USE_COLOR else ""
    DIM    = "\033[2m"  if _USE_COLOR else ""
    RED    = "\033[91m" if _USE_COLOR else ""
    GREEN  = "\033[92m" if _USE_COLOR else ""
    YELLOW = "\033[93m" if _USE_COLOR else ""
    BLUE   = "\033[94m" if _USE_COLOR else ""
    CYAN   = "\033[96m" if _USE_COLOR else ""
    GRAY   = "\033[90m" if _USE_COLOR else ""

PRIORITIES     = ("low", "medium", "high")
STATUSES       = ("pending", "done")
_PRIORITY_COLOR = {"low": C.GRAY,   "medium": C.BLUE, "high": C.RED}
_PRIORITY_ICON  = {"low": "▽",      "medium": "◇",    "high": "▲"}
_PRIORITY_RANK  = {"high": 0,       "medium": 1,       "low": 2}

@dataclass
class Task:
    title:        str
    id:           str           = field(default_factory=lambda: uuid.uuid4().hex[:8])
    description:  str           = ""
    priority:     str           = "medium"
    tags:         list          = field(default_factory=list)
    status:       str           = "pending"
    created_at:   str           = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    completed_at: Optional[str] = None

    @classmethod
    def from_dict(cls, d):
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_dict(self): return asdict(self)

    @property
    def short_id(self): return self.id[:6]


class TaskStore:
    def __init__(self, path=DATA_FILE):
        self.path = path
        self._tasks = []
        self._load()

    def _load(self):
        if self.path.exists():
            with open(self.path) as f:
                data = json.load(f)
            self._tasks = [Task.from_dict(t) for t in data.get("tasks", [])]

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump({"tasks": [t.to_dict() for t in self._tasks]}, f, indent=2)
        tmp.replace(self.path)

    def add(self, task):
        self._tasks.append(task); self._save(); return task

    def get(self, prefix):
        matches = [t for t in self._tasks if t.id.startswith(prefix.lower())]
        if len(matches) > 1:
            raise ValueError(f"Ambiguous prefix '{prefix}' matches: {', '.join(t.short_id for t in matches)}")
        return matches[0] if matches else None

    def update(self, task):
        for i, t in enumerate(self._tasks):
            if t.id == task.id:
                self._tasks[i] = task; self._save(); return
        raise KeyError(task.id)

    def delete(self, task_id):
        before = len(self._tasks)
        self._tasks = [t for t in self._tasks if t.id != task_id]
        if len(self._tasks) < before: self._save(); return True
        return False

    def filter(self, status=None, priority=None, tag=None, search=None):
        # ── YOUR CODE GOES HERE ──────────────────────────────────────────────
        # Filter `self._tasks` using AND logic across all non-None arguments.
        #   - status == "all" → skip the status check entirely
        #   - search → case-insensitive substring in title OR description
        # Return list[Task]
        raise NotImplementedError("Implement filter()")

    def sort_key(self, task):
        # ── YOUR CODE GOES HERE ──────────────────────────────────────────────
        # Return a tuple; Python sorts ascending (lower = earlier in output).
        # Suggested:
        #   status_rank   = 0 if task.status == "pending" else 1
        #   priority_rank = _PRIORITY_RANK.get(task.priority, 99)
        #   return (status_rank, priority_rank, task.created_at)
        raise NotImplementedError("Implement sort_key()")

def filter(self, status=None, priority=None, tag=None, search=None):
    result = self._tasks
    if status and status != "all":
        result = [t for t in result if t.status == status]
    if priority:
        result = [t for t in result if t.priority == priority]
    if tag:
        result = [t for t in result if tag in t.tags]
    if search:
        q = search.lower()
        result = [t for t in result if q in t.title.lower() or q in t.description.lower()]
    return result

def sort_key(self, task):
    # Option A — urgency-first (recommended for task managers)
    return (0 if task.status == "pending" else 1,
            _PRIORITY_RANK.get(task.priority, 99),
            task.created_at)
    # Option B — FIFO queue feel (flip created_at sort: use `-` for newest first)
    # return (0 if task.status == "pending" else 1, task.created_at)