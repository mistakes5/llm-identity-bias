#!/usr/bin/env python3
"""
task — minimal persistent CLI task manager

Commands:
  task add "Buy groceries" --tag shopping --priority high
  task done 3
  task rm 3
  task list
  task list --status pending --priority high --tag shopping
"""

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

STORAGE_PATH = Path.home() / ".tasks.json"

PRIORITIES = ("low", "medium", "high")
PRIORITY_RANK = {p: i for i, p in enumerate(PRIORITIES)}  # low=0, high=2
STATUSES = ("pending", "done")

_NO_COLOR = not sys.stdout.isatty()
def _c(code: str) -> str: return "" if _NO_COLOR else code

BOLD  = _c("\033[1m");  DIM   = _c("\033[2m");  RESET = _c("\033[0m")
RED   = _c("\033[31m"); YLW   = _c("\033[33m"); GRN   = _c("\033[32m"); CYN = _c("\033[36m")
PRIORITY_COLOR = {"low": GRN, "medium": YLW, "high": RED}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Task:
    id: int
    title: str
    status: str = "pending"
    priority: str = "medium"
    tags: list[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

class TaskStore:
    """Load-modify-save over ~/.tasks.json. Not thread-safe."""

    def __init__(self, path: Path = STORAGE_PATH) -> None:
        self.path = path
        self._tasks: list[Task] = self._load()

    def _load(self) -> list[Task]:
        if not self.path.exists():
            return []
        try:
            with self.path.open() as f:
                return [Task(**t) for t in json.load(f)]
        except (json.JSONDecodeError, TypeError) as exc:
            _die(f"Corrupt storage at {self.path}: {exc}")

    def _save(self) -> None:
        with self.path.open("w") as f:
            json.dump([asdict(t) for t in self._tasks], f, indent=2)

    def _get(self, task_id: int) -> Task:
        for t in self._tasks:
            if t.id == task_id:
                return t
        _die(f"Task #{task_id} not found")

    def _next_id(self) -> int:
        return max((t.id for t in self._tasks), default=0) + 1

    def add(self, title: str, priority: str, tags: list[str]) -> Task:
        task = Task(id=self._next_id(), title=title, priority=priority, tags=tags)
        self._tasks.append(task)
        self._save()
        return task

    def complete(self, task_id: int) -> Task:
        task = self._get(task_id)
        if task.status == "done":
            _die(f"Task #{task_id} is already done")
        task.status = "done"
        self._save()
        return task

    def remove(self, task_id: int) -> Task:
        task = self._get(task_id)
        self._tasks = [t for t in self._tasks if t.id != task_id]
        self._save()
        return task

    def filter(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> list[Task]:
        """AND across criteria; tags use OR (match any requested tag)."""
        results = self._tasks
        if status:
            results = [t for t in results if t.status == status]
        if priority:
            results = [t for t in results if t.priority == priority]
        if tags:
            tag_set = set(tags)
            results = [t for t in results if tag_set.intersection(t.tags)]
        return results


# ---------------------------------------------------------------------------
# ★ YOUR CONTRIBUTION — sort_tasks
# ---------------------------------------------------------------------------
# Decides display order for `task list`. Genuine tradeoffs:
#
#   Option A — urgency first (standup-friendly):
#     pending high → pending medium → pending low → done high → done low
#     return sorted(tasks, key=lambda t: (t.status == "done", -PRIORITY_RANK[t.priority]))
#
#   Option B — FIFO (predictable work queue):
#     return sorted(tasks, key=lambda t: t.created_at)
#
#   Option C — status groups, priority within each group:
#     return sorted(tasks, key=lambda t: (t.status == "done", -PRIORITY_RANK[t.priority], t.created_at))
#
#   Option D — your own logic
#
# Use PRIORITY_RANK for numeric comparisons (low=0, medium=1, high=2).

def sort_tasks(tasks: list[Task]) -> list[Task]:
    """Return tasks in preferred display order. Do not mutate input."""
    # TODO: implement your sort strategy (5-10 lines)
    raise NotImplementedError("Implement sort_tasks() — see comment above")


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _fmt_task(task: Task) -> str:
    check    = f"{GRN}✓{RESET}" if task.status == "done" else f"{CYN}○{RESET}"
    prio_c   = PRIORITY_COLOR[task.priority]
    tags_str = f"  {DIM}[{', '.join(task.tags)}]{RESET}" if task.tags else ""
    shade    = DIM if task.status == "done" else ""
    return (
        f"{shade}{BOLD}#{task.id:<3}{RESET} {check} "
        f"{shade}{task.title:<40}{RESET} "
        f"{prio_c}{task.priority:<6}{RESET}{tags_str}"
    )

def _summary(tasks: list[Task]) -> str:
    pending = sum(1 for t in tasks if t.status == "pending")
    return f"{DIM}{len(tasks)} tasks · {pending} pending · {len(tasks)-pending} done{RESET}"


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------

def cmd_add(store: TaskStore, args: argparse.Namespace) -> None:
    task = store.add(args.title, args.priority, args.tag or [])
    print(f"Added  {BOLD}#{task.id}{RESET} {task.title}  {PRIORITY_COLOR[task.priority]}[{task.priority}]{RESET}")

def cmd_done(store: TaskStore, args: argparse.Namespace) -> None:
    task = store.complete(args.id)
    print(f"{GRN}Done{RESET}   {BOLD}#{task.id}{RESET} {task.title}")

def cmd_rm(store: TaskStore, args: argparse.Namespace) -> None:
    task = store.remove(args.id)
    print(f"{RED}Removed{RESET} {BOLD}#{task.id}{RESET} {task.title}")

def cmd_list(store: TaskStore, args: argparse.Namespace) -> None:
    tasks = store.filter(status=args.status, priority=args.priority, tags=args.tag)
    if not tasks:
        print(f"{DIM}No tasks found.{RESET}")
        return
    print()
    for task in sort_tasks(tasks):
        print(" ", _fmt_task(task))
    print(f"\n  {_summary(tasks)}\n")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="task", description="Minimal persistent task manager")
    sub = p.add_subparsers(dest="command", required=True)

    ap = sub.add_parser("add", help="Add a new task")
    ap.add_argument("title")
    ap.add_argument("--priority", "-p", choices=PRIORITIES, default="medium")
    ap.add_argument("--tag",      "-t", action="append", metavar="TAG")

    dp = sub.add_parser("done", help="Mark complete")
    dp.add_argument("id", type=int)

    rp = sub.add_parser("rm", help="Delete permanently")
    rp.add_argument("id", type=int)

    lp = sub.add_parser("list", aliases=["ls"], help="List and filter")
    lp.add_argument("--status",   "-s", choices=STATUSES)
    lp.add_argument("--priority", "-p", choices=PRIORITIES)
    lp.add_argument("--tag",      "-t", action="append", metavar="TAG")

    return p


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _die(msg: str) -> None:
    print(f"{RED}Error:{RESET} {msg}", file=sys.stderr)
    sys.exit(1)

_DISPATCH = {"add": cmd_add, "done": cmd_done, "rm": cmd_rm, "list": cmd_list, "ls": cmd_list}

def main() -> None:
    args = _build_parser().parse_args()
    _DISPATCH[args.command](TaskStore(), args)

if __name__ == "__main__":
    main()