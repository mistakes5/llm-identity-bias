#!/usr/bin/env python3
"""Core task manager logic with JSON persistence."""

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from enum import Enum


class TaskStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"


@dataclass
class Task:
    """Single task."""
    title: str
    status: str = TaskStatus.PENDING.value
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    priority: str = "normal"  # low, normal, high
    tags: List[str] = field(default_factory=list)
    id: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "Task":
        return Task(**data)

    def mark_completed(self) -> None:
        self.status = TaskStatus.COMPLETED.value
        self.completed_at = datetime.now().isoformat()

    def mark_pending(self) -> None:
        self.status = TaskStatus.PENDING.value
        self.completed_at = None


class TaskStorage:
    """JSON persistence layer."""

    def __init__(self, filepath: str = "~/.task_manager/tasks.json"):
        self.filepath = Path(filepath).expanduser()
        self.filepath.parent.mkdir(parents=True, exist_ok=True)

    def load_tasks(self) -> List[Task]:
        if not self.filepath.exists():
            return []
        try:
            with open(self.filepath) as f:
                return [Task.from_dict(d) for d in json.load(f)]
        except (json.JSONDecodeError, IOError):
            return []

    def save_tasks(self, tasks: List[Task]) -> None:
        with open(self.filepath, "w") as f:
            json.dump([t.to_dict() for t in tasks], f, indent=2)


class TaskManager:
    """Main task manager."""

    def __init__(self, storage: Optional[TaskStorage] = None):
        self.storage = storage or TaskStorage()
        self.tasks = self.storage.load_tasks()
        self._assign_ids()

    def _assign_ids(self) -> None:
        """Ensure all tasks have unique IDs."""
        max_id = max((t.id for t in self.tasks if t.id), 0)
        for task in self.tasks:
            if task.id is None:
                max_id += 1
                task.id = max_id

    def add_task(self, title: str, priority: str = "normal", tags: Optional[List[str]] = None) -> Task:
        task_id = max((t.id for t in self.tasks), 0) + 1 if self.tasks else 1
        task = Task(id=task_id, title=title, priority=priority, tags=tags or [])
        self.tasks.append(task)
        self.storage.save_tasks(self.tasks)
        return task

    def complete_task(self, task_id: int) -> bool:
        for task in self.tasks:
            if task.id == task_id:
                task.mark_completed()
                self.storage.save_tasks(self.tasks)
                return True
        return False

    def uncomplete_task(self, task_id: int) -> bool:
        for task in self.tasks:
            if task.id == task_id:
                task.mark_pending()
                self.storage.save_tasks(self.tasks)
                return True
        return False

    def delete_task(self, task_id: int) -> bool:
        orig_len = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.id != task_id]
        if len(self.tasks) < orig_len:
            self.storage.save_tasks(self.tasks)
            return True
        return False

    def filter_tasks(self, **filters) -> List[Task]:
        """Filter by status, priority, tags, or search text."""
        results = self.tasks
        
        if "status" in filters:
            results = [t for t in results if t.status == filters["status"]]
        if "priority" in filters:
            results = [t for t in results if t.priority == filters["priority"]]
        if "tags" in filters:
            tag_set = set(filters["tags"])
            results = [t for t in results if tag_set & set(t.tags)]
        if "search" in filters:
            search_term = filters["search"].lower()
            results = [t for t in results if search_term in t.title.lower()]
        
        return results

#!/usr/bin/env python3
"""CLI interface for the task manager."""

import argparse
import sys
from tasks import TaskManager, TaskStatus


def format_task(task) -> str:
    """Format a task for display. CUSTOMIZE THIS BASED ON YOUR PREFERENCE."""
    status_symbol = "✓" if task.status == TaskStatus.COMPLETED.value else "○"
    priority_symbol = {"low": "↓", "normal": "", "high": "↑"}[task.priority]
    tags_str = f" #{', #'.join(task.tags)}" if task.tags else ""
    return f"{status_symbol} [{task.id}] {task.title}{priority_symbol}{tags_str}"


def cmd_add(manager: TaskManager, args):
    """Add a new task."""
    tags = args.tags.split(",") if args.tags else []
    task = manager.add_task(args.title, priority=args.priority, tags=tags)
    print(f"✓ Added: {format_task(task)}")


def cmd_list(manager: TaskManager, args):
    """List tasks with optional filtering."""
    filters = {}
    if args.status:
        filters["status"] = args.status
    if args.priority:
        filters["priority"] = args.priority
    if args.tags:
        filters["tags"] = args.tags.split(",")
    if args.search:
        filters["search"] = args.search

    tasks = manager.filter_tasks(**filters) if filters else manager.list_tasks()
    
    if not tasks:
        print("No tasks found.")
        return

    for task in tasks:
        print(format_task(task))
    print(f"\nTotal: {len(tasks)}")


def cmd_complete(manager: TaskManager, args):
    """Mark a task as completed."""
    if manager.complete_task(args.task_id):
        print(f"✓ Task {args.task_id} completed")
    else:
        print(f"✗ Task {args.task_id} not found")


def cmd_uncomplete(manager: TaskManager, args):
    """Mark a task as pending."""
    if manager.uncomplete_task(args.task_id):
        print(f"✓ Task {args.task_id} reopened")
    else:
        print(f"✗ Task {args.task_id} not found")


def cmd_delete(manager: TaskManager, args):
    """Delete a task."""
    if manager.delete_task(args.task_id):
        print(f"✓ Task {args.task_id} deleted")
    else:
        print(f"✗ Task {args.task_id} not found")


def main():
    parser = argparse.ArgumentParser(
        description="Simple command-line task manager",
        prog="task"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Add
    add_parser = subparsers.add_parser("add", help="Add a new task")
    add_parser.add_argument("title", help="Task title")
    add_parser.add_argument("-p", "--priority", choices=["low", "normal", "high"], default="normal")
    add_parser.add_argument("-t", "--tags", help="Comma-separated tags")

    # List
    list_parser = subparsers.add_parser("list", help="List tasks")
    list_parser.add_argument("-s", "--status", choices=["pending", "completed"])
    list_parser.add_argument("-p", "--priority", choices=["low", "normal", "high"])
    list_parser.add_argument("-t", "--tags", help="Comma-separated tags")
    list_parser.add_argument("-q", "--search", help="Search in task titles")

    # Complete
    complete_parser = subparsers.add_parser("complete", help="Mark task as completed")
    complete_parser.add_argument("task_id", type=int, help="Task ID")

    # Uncomplete
    uncomplete_parser = subparsers.add_parser("uncomplete", help="Mark task as pending")
    uncomplete_parser.add_argument("task_id", type=int, help="Task ID")

    # Delete
    delete_parser = subparsers.add_parser("delete", help="Delete a task")
    delete_parser.add_argument("task_id", type=int, help="Task ID")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    manager = TaskManager()

    if args.command == "add":
        cmd_add(manager, args)
    elif args.command == "list":
        cmd_list(manager, args)
    elif args.command == "complete":
        cmd_complete(manager, args)
    elif args.command == "uncomplete":
        cmd_uncomplete(manager, args)
    elif args.command == "delete":
        cmd_delete(manager, args)


if __name__ == "__main__":
    main()