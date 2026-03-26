"""task_manager — a persistent CLI task manager."""
__version__ = "1.0.0"

from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


PRIORITIES = ("low", "medium", "high")
STATUSES   = ("pending", "done")

PRIORITY_RANK = {"low": 0, "medium": 1, "high": 2}


@dataclass
class Task:
    title: str
    id: str                   = field(default_factory=lambda: uuid.uuid4().hex[:8])
    tags: list[str]           = field(default_factory=list)
    priority: str             = "medium"
    status: str               = "pending"
    created_at: str           = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    # ── lifecycle ─────────────────────────────────────────────────────────────
    def complete(self) -> None:
        self.status = "done"
        self.completed_at = datetime.now().isoformat()

    # ── serialization ─────────────────────────────────────────────────────────
    def to_dict(self) -> dict:
        return {
            "id":           self.id,
            "title":        self.title,
            "tags":         self.tags,
            "priority":     self.priority,
            "status":       self.status,
            "created_at":   self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Task:
        return cls(**data)


# ── filtering ─────────────────────────────────────────────────────────────────

def filter_tasks(
    tasks: list[Task],
    *,
    status:   str | None       = None,
    priority: str | None       = None,
    tags:     list[str] | None = None,
) -> list[Task]:
    """
    Return the subset of *tasks* that match all supplied predicates.

    TODO ── implement this function (5–10 lines).

    Parameters
    ----------
    tasks    : full task list from storage
    status   : "pending" | "done" | None  (None = no filter)
    priority : "low" | "medium" | "high" | None
    tags     : list of tag strings | None

    Design questions to consider:
    - Multiple tags: should a task need ALL supplied tags (AND) or just one (OR)?
    - Should tag matching be case-insensitive?
    - What order should surviving tasks be returned in?
      (e.g. pending before done, then by priority descending)
    """
    # ── your code here ────────────────────────────────────────────────────────
    ...

import json
from pathlib import Path

from .models import Task

DEFAULT_PATH = Path.home() / ".task_manager" / "tasks.json"


class TaskStore:
    def __init__(self, path: Path = DEFAULT_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    # ── raw I/O ───────────────────────────────────────────────────────────────
    def load(self) -> list[Task]:
        if not self.path.exists():
            return []
        with self.path.open() as fh:
            return [Task.from_dict(d) for d in json.load(fh)]

    def save(self, tasks: list[Task]) -> None:
        with self.path.open("w") as fh:
            json.dump([t.to_dict() for t in tasks], fh, indent=2)

    # ── mutations ─────────────────────────────────────────────────────────────
    def add(self, task: Task) -> Task:
        tasks = self.load()
        tasks.append(task)
        self.save(tasks)
        return task

    def update(self, task: Task) -> bool:
        tasks = self.load()
        for i, t in enumerate(tasks):
            if t.id == task.id:
                tasks[i] = task
                self.save(tasks)
                return True
        return False

    def delete(self, prefix: str) -> bool:
        tasks  = self.load()
        kept   = [t for t in tasks if not t.id.startswith(prefix)]
        if len(kept) == len(tasks):
            return False
        self.save(kept)
        return True

    # ── queries ───────────────────────────────────────────────────────────────
    def find(self, prefix: str) -> Optional[Task]:
        matches = [t for t in self.load() if t.id.startswith(prefix)]
        return matches[0] if len(matches) == 1 else None

from .models import Task, PRIORITY_RANK

# ANSI colour helpers
_RESET  = "\033[0m"
_BOLD   = "\033[1m"
_DIM    = "\033[2m"
_RED    = "\033[31m"
_YELLOW = "\033[33m"
_CYAN   = "\033[36m"
_GREEN  = "\033[32m"
_WHITE  = "\033[37m"


def _priority_colour(p: str) -> str:
    return {
        "high":   f"{_RED}{_BOLD}HIGH  {_RESET}",
        "medium": f"{_YELLOW}MEDIUM{_RESET}",
        "low":    f"{_CYAN}LOW   {_RESET}",
    }.get(p, p)


def _status_colour(s: str) -> str:
    if s == "done":
        return f"{_GREEN}done   {_RESET}"
    return f"{_WHITE}pending{_RESET}"


def _fmt_date(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        return datetime.fromisoformat(iso).strftime("%b %d %H:%M")
    except ValueError:
        return iso[:16]


def print_tasks(tasks: list[Task]) -> None:
    if not tasks:
        print(f"  {_DIM}No tasks found.{_RESET}")
        return

    # Column widths
    id_w    = 8
    pri_w   = 6
    stat_w  = 7
    tag_w   = 16
    date_w  = 12

    # Header
    sep = "─"
    print(
        f"\n  {_BOLD}"
        f"{'ID':<{id_w}}  {'PRI':<{pri_w}}  {'STATUS':<{stat_w}}  "
        f"{'TAGS':<{tag_w}}  {'CREATED':<{date_w}}  TITLE"
        f"{_RESET}"
    )
    print(
        f"  {sep*id_w}  {sep*pri_w}  {sep*stat_w}  "
        f"{sep*tag_w}  {sep*date_w}  {sep*30}"
    )

    for t in tasks:
        tags_str   = ",".join(t.tags)[:tag_w] if t.tags else _DIM + "—" + _RESET
        title_str  = (_DIM if t.status == "done" else "") + t.title + _RESET
        print(
            f"  {_BOLD}{t.id}{_RESET}  "
            f"{_priority_colour(t.priority)}  "
            f"{_status_colour(t.status)}  "
            f"{tags_str:<{tag_w}}  "
            f"{_fmt_date(t.created_at):<{date_w}}  "
            f"{title_str}"
        )
    print()


def print_success(msg: str) -> None:
    print(f"  {_GREEN}✓{_RESET}  {msg}")


def print_error(msg: str) -> None:
    print(f"  {_RED}✗{_RESET}  {msg}")

import argparse
import sys

from .models import Task, filter_tasks, PRIORITIES, STATUSES
from .storage import TaskStore
from .display import print_tasks, print_success, print_error


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tasks",
        description="A persistent command-line task manager.",
    )
    sub = p.add_subparsers(dest="command", metavar="COMMAND")

    # ── add ───────────────────────────────────────────────────────────────────
    add_p = sub.add_parser("add", help="Add a new task")
    add_p.add_argument("title", help="Task description")
    add_p.add_argument(
        "--tags", "-t",
        nargs="+", default=[],
        metavar="TAG",
        help="One or more tags",
    )
    add_p.add_argument(
        "--priority", "-p",
        choices=PRIORITIES, default="medium",
        help="Priority level (default: medium)",
    )

    # ── done ──────────────────────────────────────────────────────────────────
    done_p = sub.add_parser("done", help="Mark a task as completed")
    done_p.add_argument("id", help="Task ID prefix (min 3 chars)")

    # ── delete ────────────────────────────────────────────────────────────────
    del_p = sub.add_parser("delete", aliases=["rm"], help="Delete a task")
    del_p.add_argument("id", help="Task ID prefix")

    # ── list ──────────────────────────────────────────────────────────────────
    list_p = sub.add_parser("list", aliases=["ls"], help="List tasks")
    list_p.add_argument(
        "--status", "-s",
        choices=STATUSES,
        help="Filter by status",
    )
    list_p.add_argument(
        "--priority", "-p",
        choices=PRIORITIES,
        help="Filter by priority",
    )
    list_p.add_argument(
        "--tag", "-t",
        nargs="+", dest="tags",
        metavar="TAG",
        help="Filter by one or more tags",
    )

    return p


def main() -> None:
    parser  = _build_parser()
    args    = parser.parse_args()
    store   = TaskStore()

    if args.command == "add":
        task = Task(
            title    = args.title,
            tags     = [t.lower() for t in args.tags],
            priority = args.priority,
        )
        store.add(task)
        print_success(f"Added [{task.id}] — {task.title!r}")

    elif args.command == "done":
        task = store.find(args.id)
        if not task:
            print_error(f"No unique task found for prefix '{args.id}'")
            sys.exit(1)
        task.complete()
        store.update(task)
        print_success(f"Completed [{task.id}] — {task.title!r}")

    elif args.command in ("delete", "rm"):
        if not store.delete(args.id):
            print_error(f"No task found for prefix '{args.id}'")
            sys.exit(1)
        print_success(f"Deleted task(s) matching '{args.id}'")

    elif args.command in ("list", "ls", None):
        # None = bare `python tasks.py` with no subcommand → default to list
        status   = getattr(args, "status",   None)
        priority = getattr(args, "priority", None)
        tags     = getattr(args, "tags",     None)

        all_tasks     = store.load()
        visible_tasks = filter_tasks(
            all_tasks,
            status=status,
            priority=priority,
            tags=[t.lower() for t in tags] if tags else None,
        )
        print_tasks(visible_tasks)

    else:
        parser.print_help()

#!/usr/bin/env python3
"""Entry point — run as `python tasks.py <command>`."""
from task_manager.cli import main

if __name__ == "__main__":
    main()

def filter_tasks(tasks, *, status=None, priority=None, tags=None):
    # status   — if provided, keep only tasks where task.status == status
    # priority — if provided, keep only tasks where task.priority == priority
    # tags     — list or None; the interesting question is: AND or OR?
    #
    # If you want `--tag work bug` to mean
    #   AND → task must have BOTH "work" AND "bug"
    #   OR  → task just needs one of them
    #
    # You can also control sort order here — e.g.:
    #   pending before done, then high → medium → low priority
    ...