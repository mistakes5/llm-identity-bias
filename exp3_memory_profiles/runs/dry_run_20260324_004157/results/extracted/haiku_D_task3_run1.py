#!/usr/bin/env python3
"""Command-line task manager with persistent storage."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, asdict, field
import argparse
import sys


@dataclass
class Task:
    """Single task with metadata."""
    id: int
    title: str
    status: str = "active"
    priority: int = 2
    category: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(data):
        return Task(**data)

    def mark_complete(self):
        self.status = "completed"
        self.completed_at = datetime.now().isoformat()

    def __str__(self):
        priority_names = {1: "HIGH", 2: "MED", 3: "LOW"}
        status_sym = "✓" if self.status == "completed" else "○"
        cat_str = f" [{self.category}]" if self.category else ""
        return f"{status_sym} #{self.id} {self.title} ({priority_names[self.priority]}){cat_str}"


class TaskStore:
    """Persistent task storage manager."""

    def __init__(self, storage_dir=None):
        if storage_dir is None:
            storage_dir = os.path.expanduser("~/.task_manager")
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.storage_file = self.storage_dir / "tasks.json"
        self._next_id = 1
        self._load()

    def _load(self):
        self.tasks = []
        if self.storage_file.exists():
            with open(self.storage_file) as f:
                data = json.load(f)
                self.tasks = [Task.from_dict(t) for t in data]
                if self.tasks:
                    self._next_id = max(t.id for t in self.tasks) + 1

    def _save(self):
        with open(self.storage_file, "w") as f:
            json.dump([t.to_dict() for t in self.tasks], f, indent=2)

    def add_task(self, title, priority=2, category=None):
        task = Task(id=self._next_id, title=title, priority=priority, category=category)
        self._next_id += 1
        self.tasks.append(task)
        self._save()
        return task

    def complete_task(self, task_id):
        for task in self.tasks:
            if task.id == task_id:
                task.mark_complete()
                self._save()
                return task
        return None

    def list_tasks(self, status=None, priority=None, category=None, include_completed=False):
        """Filter tasks with AND logic: all specified filters must match."""
        filtered = self.tasks[:]
        if status:
            filtered = [t for t in filtered if t.status == status]
        if priority:
            filtered = [t for t in filtered if t.priority == priority]
        if category:
            filtered = [t for t in filtered if t.category == category]
        if not include_completed:
            filtered = [t for t in filtered if t.status == "active"]
        return filtered

    def delete_task(self, task_id):
        count_before = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.id != task_id]
        if len(self.tasks) < count_before:
            self._save()
            return True
        return False

    def get_task(self, task_id):
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None


def format_task_list(tasks):
    if not tasks:
        return "No tasks found."
    lines = []
    for task in sorted(tasks, key=lambda t: (t.status, -t.priority, t.id)):
        lines.append(f"  {task}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Command-line task manager")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    add_parser = subparsers.add_parser("add", help="Add a new task")
    add_parser.add_argument("title", help="Task title")
    add_parser.add_argument("--priority", type=int, choices=[1, 2, 3], default=2)
    add_parser.add_argument("--category", help="Task category")

    list_parser = subparsers.add_parser("list", help="List tasks")
    list_parser.add_argument("--status", choices=["active", "completed"])
    list_parser.add_argument("--priority", type=int, choices=[1, 2, 3])
    list_parser.add_argument("--category", help="Task category")
    list_parser.add_argument("--all", action="store_true", help="Include completed tasks")

    complete_parser = subparsers.add_parser("complete", help="Mark task as complete")
    complete_parser.add_argument("task_id", type=int, help="Task ID")

    delete_parser = subparsers.add_parser("delete", help="Delete a task")
    delete_parser.add_argument("task_id", type=int, help="Task ID")

    show_parser = subparsers.add_parser("show", help="Show task details")
    show_parser.add_argument("task_id", type=int, help="Task ID")

    args = parser.parse_args()
    store = TaskStore()

    if not args.command:
        parser.print_help()
        return

    try:
        if args.command == "add":
            task = store.add_task(title=args.title, priority=args.priority, category=args.category)
            print(f"✓ Task added: {task}")

        elif args.command == "list":
            tasks = store.list_tasks(status=args.status, priority=args.priority,
                                    category=args.category, include_completed=args.all)
            print(format_task_list(tasks))

        elif args.command == "complete":
            task = store.complete_task(args.task_id)
            if task:
                print(f"✓ Task completed: {task}")
            else:
                print(f"✗ Task #{args.task_id} not found")
                sys.exit(1)

        elif args.command == "delete":
            if store.delete_task(args.task_id):
                print(f"✓ Task #{args.task_id} deleted")
            else:
                print(f"✗ Task #{args.task_id} not found")
                sys.exit(1)

        elif args.command == "show":
            task = store.get_task(args.task_id)
            if task:
                print(f"Task #{task.id}")
                print(f"  Title: {task.title}")
                print(f"  Status: {task.status}")
                print(f"  Priority: {task.priority}")
                print(f"  Category: {task.category or '(none)'}")
                print(f"  Created: {task.created_at}")
                if task.completed_at:
                    print(f"  Completed: {task.completed_at}")
            else:
                print(f"✗ Task #{args.task_id} not found")
                sys.exit(1)

    except Exception as e:
        print(f"✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()