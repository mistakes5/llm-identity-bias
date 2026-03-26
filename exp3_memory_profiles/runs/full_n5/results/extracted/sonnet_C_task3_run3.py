#!/usr/bin/env python3
"""
task_manager.py — A persistent CLI task manager.

Usage:
  python task_manager.py add "Buy groceries" --tag shopping --priority high
  python task_manager.py list
  python task_manager.py list --status done
  python task_manager.py list --tag shopping --priority high
  python task_manager.py complete 1
  python task_manager.py delete 3
"""

import json
import argparse
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

STORE_PATH = Path.home() / ".task_manager.json"
PRIORITIES = ["low", "medium", "high"]
STATUSES   = ["todo", "done"]


# ── Data model ────────────────────────────────────────────────────────────────

@dataclass
class Task:
    id: int
    title: str
    status: str = "todo"
    priority: str = "medium"
    tags: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    def complete(self):
        self.status = "done"
        self.completed_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(**data)


# ── Persistence ───────────────────────────────────────────────────────────────

class TaskStore:
    """Loads and saves tasks to a JSON file on disk."""

    def __init__(self, path: Path = STORE_PATH):
        self.path = path
        self._tasks: list = []
        self._next_id: int = 1
        self._load()

    def _load(self):
        if self.path.exists():
            data = json.loads(self.path.read_text())
            self._tasks = [Task.from_dict(t) for t in data.get("tasks", [])]
            self._next_id = data.get("next_id", 1)

    def _save(self):
        self.path.write_text(
            json.dumps(
                {"tasks": [t.to_dict() for t in self._tasks], "next_id": self._next_id},
                indent=2,
            )
        )

    def add(self, title: str, priority: str = "medium", tags: list = None) -> Task:
        task = Task(id=self._next_id, title=title, priority=priority, tags=tags or [])
        self._tasks.append(task)
        self._next_id += 1
        self._save()
        return task

    def complete(self, task_id: int) -> Optional[Task]:
        task = self.get(task_id)
        if task:
            task.complete()
            self._save()
        return task

    def delete(self, task_id: int) -> Optional[Task]:
        task = self.get(task_id)
        if task:
            self._tasks.remove(task)
            self._save()
        return task

    def get(self, task_id: int) -> Optional[Task]:
        return next((t for t in self._tasks if t.id == task_id), None)

    def all(self) -> list:
        return list(self._tasks)


# ── Filtering ─────────────────────────────────────────────────────────────────

def filter_tasks(
    tasks: list,
    status: Optional[str],
    tag: Optional[str],
    priority: Optional[str],
) -> list:
    """
    Return tasks that match ALL provided filters (AND logic).
    Any filter set to None is ignored.

    TODO: Implement this function (~5-8 lines).

    Hints:
      - task.status == status      → filter by completion state
      - tag in task.tags           → filter by tag (exact match)
      - task.priority == priority  → filter by priority level
      - All active filters must match (AND logic)
      - A list comprehension works well here

    Example:
      filter_tasks(tasks, status="todo", tag="work", priority=None)
      → only todo tasks that also have the "work" tag
    """
    # ← Your implementation goes here
    return tasks  # placeholder: shows all tasks until you implement this


# ── Display helpers ───────────────────────────────────────────────────────────

RESET  = "\033[0m";  BOLD   = "\033[1m";  DIM    = "\033[2m"
RED    = "\033[91m"; YELLOW = "\033[93m"; GREEN  = "\033[92m"; CYAN = "\033[96m"
PRIORITY_COLOR = {"high": RED, "medium": YELLOW, "low": GREEN}

def fmt_priority(p):
    return f"{PRIORITY_COLOR.get(p, '')}{p}{RESET}"

def fmt_tags(tags):
    return "  " + " ".join(f"{CYAN}#{t}{RESET}" for t in tags) if tags else ""

def print_task(task):
    icon  = f"{GREEN}✓{RESET}" if task.status == "done" else f"{DIM}○{RESET}"
    title = f"{DIM}{task.title}{RESET}" if task.status == "done" else task.title
    print(f"  {icon}  [{task.id:>3}]  {title}  {fmt_priority(task.priority)}{fmt_tags(task.tags)}")

def print_tasks(tasks):
    if not tasks:
        print(f"\n  {DIM}No tasks found.{RESET}\n"); return
    todo = [t for t in tasks if t.status == "todo"]
    done = [t for t in tasks if t.status == "done"]
    if todo: print(f"\n{BOLD}  TODO{RESET}"); [print_task(t) for t in todo]
    if done: print(f"\n{BOLD}  DONE{RESET}"); [print_task(t) for t in done]
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(prog="tasks", description="Persistent CLI task manager")
    sub = p.add_subparsers(dest="command")

    add_p = sub.add_parser("add", help="Add a new task")
    add_p.add_argument("title")
    add_p.add_argument("--priority", "-p", choices=PRIORITIES, default="medium")
    add_p.add_argument("--tag", "-t", dest="tags", action="append", default=[])

    done_p = sub.add_parser("complete", help="Mark a task as done")
    done_p.add_argument("id", type=int)

    del_p = sub.add_parser("delete", help="Remove a task")
    del_p.add_argument("id", type=int)

    list_p = sub.add_parser("list", help="List tasks")
    list_p.add_argument("--status",   "-s", choices=STATUSES,  default=None)
    list_p.add_argument("--tag",      "-t",                     default=None)
    list_p.add_argument("--priority", "-p", choices=PRIORITIES, default=None)

    return p


def main():
    parser = build_parser()
    args   = parser.parse_args()
    store  = TaskStore()

    if args.command == "add":
        task = store.add(args.title, priority=args.priority, tags=args.tags)
        print(f"\n  {GREEN}✓{RESET} Added [{task.id}] {task.title}  {fmt_priority(task.priority)}\n")

    elif args.command == "complete":
        task = store.complete(args.id)
        print(f"\n  {GREEN}✓{RESET} Completed [{task.id}] {task.title}\n" if task else f"\n  ✗ Task #{args.id} not found.\n")

    elif args.command == "delete":
        task = store.delete(args.id)
        print(f"\n  {GREEN}✓{RESET} Deleted [{task.id}] {task.title}\n" if task else f"\n  ✗ Task #{args.id} not found.\n")

    elif args.command == "list":
        print_tasks(filter_tasks(store.all(), args.status, args.tag, args.priority))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

def filter_tasks(tasks, status, tag, priority):
    result = tasks
    if status   is not None: result = [t for t in result if ...]
    if tag      is not None: result = [t for t in result if ...]
    if priority is not None: result = [t for t in result if ...]
    return result