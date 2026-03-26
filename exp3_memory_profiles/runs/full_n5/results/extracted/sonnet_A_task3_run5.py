"""Task domain model — pure data, no I/O."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional

VALID_STATUSES  = ("pending", "done")
VALID_PRIORITIES = ("low", "medium", "high")
PRIORITY_RANK   = {"low": 0, "medium": 1, "high": 2}


@dataclass
class Task:
    id: int
    title: str
    status: str = "pending"       # "pending" | "done"
    priority: str = "medium"      # "low" | "medium" | "high"
    tags: list[str] = field(default_factory=list)
    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    def complete(self) -> None:
        self.status = "done"
        self.completed_at = datetime.now().isoformat()

    def reopen(self) -> None:
        self.status = "pending"
        self.completed_at = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Task:
        return cls(
            id=data["id"],
            title=data["title"],
            status=data.get("status", "pending"),
            priority=data.get("priority", "medium"),
            tags=data.get("tags", []),
            notes=data.get("notes", ""),
            created_at=data.get("created_at", datetime.now().isoformat()),
            completed_at=data.get("completed_at"),
        )

    @property
    def priority_rank(self) -> int:
        return PRIORITY_RANK.get(self.priority, 1)

"""Atomic JSON persistence. Tasks survive crashes mid-write."""

import json
import os
from pathlib import Path

from .models import Task

# Override with TASKS_FILE env var, e.g. for testing
_DEFAULT = Path.home() / ".local" / "share" / "tasks" / "tasks.json"


class TaskStore:
    def __init__(self, path: Optional[Path] = None) -> None:
        env_path = os.environ.get("TASKS_FILE")
        self.path = Path(env_path) if env_path else (path or _DEFAULT)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._tasks: list[Task] = []
        self._load()

    # ── read ─────────────────────────────────────────────────────────────────

    def all(self) -> list[Task]:
        return list(self._tasks)

    def get(self, task_id: int) -> Optional[Task]:
        return next((t for t in self._tasks if t.id == task_id), None)

    # ── write ────────────────────────────────────────────────────────────────

    def add(self, task: Task) -> Task:
        task.id = self._next_id()
        self._tasks.append(task)
        self._save()
        return task

    def update(self, task: Task) -> None:
        idx = next((i for i, t in enumerate(self._tasks) if t.id == task.id), None)
        if idx is None:
            raise KeyError(f"No task with id={task.id}")
        self._tasks[idx] = task
        self._save()

    def delete(self, task_id: int) -> bool:
        before = len(self._tasks)
        self._tasks = [t for t in self._tasks if t.id != task_id]
        if len(self._tasks) < before:
            self._save()
            return True
        return False

    # ── internals ────────────────────────────────────────────────────────────

    def _load(self) -> None:
        if self.path.exists():
            with open(self.path, encoding="utf-8") as fh:
                raw = json.load(fh)
            self._tasks = [Task.from_dict(d) for d in raw]
        else:
            self._tasks = []

    def _save(self) -> None:
        # Write to a sibling .tmp file, then atomically rename — safe on crash
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump([t.to_dict() for t in self._tasks], fh, indent=2)
        tmp.replace(self.path)

    def _next_id(self) -> int:
        return max((t.id for t in self._tasks), default=0) + 1

"""ANSI terminal rendering. Strips color when stdout is not a TTY."""

import sys

# ── color support ─────────────────────────────────────────────────────────────
_USE_COLOR = sys.stdout.isatty()

def _c(code: str) -> str:
    return code if _USE_COLOR else ""

RESET  = _c("\033[0m");  BOLD = _c("\033[1m");  DIM = _c("\033[2m")
RED    = _c("\033[31m"); GREEN = _c("\033[32m"); YELLOW = _c("\033[33m")
CYAN   = _c("\033[36m"); GRAY  = _c("\033[90m"); WHITE  = _c("\033[37m")

PRIORITY_COLOR = {"high": RED, "medium": YELLOW, "low": GREEN}
STATUS_ICON    = {"pending": "○", "done": "●"}

# ── helpers ───────────────────────────────────────────────────────────────────

def _fmt_date(iso: str | None) -> str:
    if not iso:
        return ""
    return datetime.fromisoformat(iso).strftime("%b %d, %Y")

# ── public API ────────────────────────────────────────────────────────────────

def render_task(task: Task, verbose: bool = False) -> str:
    icon    = STATUS_ICON[task.status]
    pcolor  = PRIORITY_COLOR.get(task.priority, WHITE)
    fade    = DIM if task.status == "done" else ""
    tags    = "  ".join(f"{CYAN}#{t}{RESET}" for t in task.tags)
    badge   = f"{pcolor}[{task.priority}]{RESET}"

    line = (
        f"  {BOLD}{pcolor}{icon}{RESET} "
        f"{GRAY}#{task.id:<3}{RESET} "
        f"{fade}{task.title}{RESET}"
        f"  {badge}"
        + (f"  {tags}" if tags else "")
    )

    if task.status == "done" and task.completed_at:
        line += f"  {GRAY}✓ {_fmt_date(task.completed_at)}{RESET}"

    if verbose and task.notes:
        line += f"\n      {GRAY}{task.notes}{RESET}"

    return line


def render_list(tasks: list[Task], verbose: bool = False) -> None:
    if not tasks:
        print(f"\n  {GRAY}No tasks match.{RESET}\n")
        return

    pending = sorted(
        [t for t in tasks if t.status == "pending"],
        key=lambda t: -t.priority_rank,
    )
    done = [t for t in tasks if t.status == "done"]

    if pending:
        print(f"\n{BOLD}Pending  ({len(pending)}){RESET}")
        for t in pending:
            print(render_task(t, verbose))

    if done:
        print(f"\n{BOLD}{GRAY}Done  ({len(done)}){RESET}")
        for t in done:
            print(render_task(t, verbose))

    print()

"""
Filter predicate — decides which tasks survive a `list` query.

Called as:  matches(task, status=None, priority=None, tag=None, search=None)

You implement this function. It's the only non-trivial logic left.
"""


def matches(task: Task, **criteria) -> bool:
    """
    Return True if `task` satisfies ALL supplied criteria.

    Criteria kwargs (all optional — None means "don't filter on this"):
        status   (str)  — exact match: "pending" or "done"
        priority (str)  — exact match: "low", "medium", or "high"
        tag      (str)  — task's tag list must contain this tag
        search   (str)  — free-text match against task.title

    TODO: implement the body below.
    """
    raise NotImplementedError

"""CLI entry point.  python -m task_manager <command> [args]"""

import argparse

from .display import BOLD, CYAN, GRAY, GREEN, RED, RESET, render_list, render_task
from .models import Task, VALID_PRIORITIES, VALID_STATUSES
from .store import TaskStore
from . import filters


store = TaskStore()


# ── command handlers ──────────────────────────────────────────────────────────

def cmd_add(args: argparse.Namespace) -> None:
    tags = [t.strip().lstrip("#") for t in args.tag] if args.tag else []
    task = store.add(Task(
        id=0,
        title=args.title,
        priority=args.priority,
        tags=tags,
        notes=args.notes or "",
    ))
    print(f"\n  {GREEN}✓{RESET} Added {BOLD}#{task.id}{RESET} — {task.title}\n")


def cmd_done(args: argparse.Namespace) -> None:
    for task_id in args.ids:
        task = store.get(task_id)
        if task is None:
            print(f"  {RED}✗{RESET} Task #{task_id} not found.", file=sys.stderr)
            continue
        task.complete()
        store.update(task)
        print(f"  {GREEN}✓{RESET} Marked #{task_id} done — {GRAY}{task.title}{RESET}")
    print()


def cmd_reopen(args: argparse.Namespace) -> None:
    task = store.get(args.id)
    if task is None:
        sys.exit(f"Task #{args.id} not found.")
    task.reopen()
    store.update(task)
    print(f"\n  {CYAN}↩{RESET} Reopened #{args.id} — {task.title}\n")


def cmd_delete(args: argparse.Namespace) -> None:
    if not store.delete(args.id):
        sys.exit(f"Task #{args.id} not found.")
    print(f"\n  {RED}✗{RESET} Deleted #{args.id}\n")


def cmd_list(args: argparse.Namespace) -> None:
    criteria = {
        "status":   args.status,
        "priority": args.priority,
        "tag":      args.tag,
        "search":   args.search,
    }
    # Drop None values so matches() only receives active filters
    active = {k: v for k, v in criteria.items() if v is not None}

    all_tasks = store.all()
    filtered = [t for t in all_tasks if filters.matches(t, **active)] if active else all_tasks
    render_list(filtered, verbose=args.verbose)


# ── argument parser ───────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m task_manager",
        description="A minimal persistent task manager.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # add
    add = sub.add_parser("add", help="Create a new task")
    add.add_argument("title", help="Task title (quote multi-word titles)")
    add.add_argument("-p", "--priority", choices=VALID_PRIORITIES, default="medium")
    add.add_argument("-t", "--tag", action="append", metavar="TAG",
                     help="Tag (repeatable: -t work -t urgent)")
    add.add_argument("-n", "--notes", help="Optional longer description")

    # done
    done = sub.add_parser("done", help="Mark one or more tasks complete")
    done.add_argument("ids", nargs="+", type=int, metavar="ID")

    # reopen
    reopen = sub.add_parser("reopen", help="Return a done task to pending")
    reopen.add_argument("id", type=int)

    # delete
    delete = sub.add_parser("delete", help="Permanently remove a task")
    delete.add_argument("id", type=int)

    # list
    lst = sub.add_parser("list", help="List and filter tasks")
    lst.add_argument("-s", "--status",   choices=VALID_STATUSES,  default=None)
    lst.add_argument("-p", "--priority", choices=VALID_PRIORITIES, default=None)
    lst.add_argument("-t", "--tag",      default=None, metavar="TAG")
    lst.add_argument("-q", "--search",   default=None, metavar="TEXT")
    lst.add_argument("-v", "--verbose",  action="store_true")

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    dispatch = {
        "add":    cmd_add,
        "done":   cmd_done,
        "reopen": cmd_reopen,
        "delete": cmd_delete,
        "list":   cmd_list,
    }
    dispatch[args.command](args)


if __name__ == "__main__":
    main()

# task_manager/__init__.py

def matches(task: Task, **criteria) -> bool:
    """
    Return True if `task` satisfies ALL supplied criteria.
    Keys: status, priority, tag, search  (all optional)
    """
    raise NotImplementedError