#!/usr/bin/env python3
"""
Command-line task manager with persistent storage.
Tasks are stored in a JSON file and can be added, completed, listed, and filtered.
"""

import json
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict, field
from enum import Enum


class TaskStatus(Enum):
    """Task status enumeration."""
    PENDING = "pending"
    COMPLETED = "completed"


@dataclass
class Task:
    """Represents a single task."""
    title: str
    description: str = ""
    status: str = TaskStatus.PENDING.value
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    id: int = field(default_factory=int)

    def to_dict(self) -> Dict:
        """Convert task to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> "Task":
        """Create task from dictionary."""
        return cls(**data)

    def mark_completed(self) -> None:
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED.value
        self.completed_at = datetime.now().isoformat()

    def __str__(self) -> str:
        """Format task for display."""
        status_symbol = "✓" if self.status == TaskStatus.COMPLETED.value else "○"
        created = datetime.fromisoformat(self.created_at).strftime("%Y-%m-%d %H:%M")
        result = f"[{status_symbol}] #{self.id} {self.title} ({created})"
        if self.description:
            result += f"\n    └─ {self.description}"
        return result


class TaskStorage:
    """Manages task persistence using JSON."""

    def __init__(self, filepath: Optional[Path] = None):
        """Initialize storage with a data file path."""
        if filepath is None:
            filepath = Path.home() / ".task_manager" / "tasks.json"

        self.filepath = filepath
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        self._next_id = 1
        self._load()

    def _load(self) -> None:
        """Load tasks from file."""
        if self.filepath.exists():
            try:
                with open(self.filepath, 'r') as f:
                    data = json.load(f)
                    self.tasks = [Task.from_dict(t) for t in data["tasks"]]
                    self._next_id = data.get("next_id", len(self.tasks) + 1)
            except (json.JSONDecodeError, KeyError):
                self.tasks = []
                self._next_id = 1
        else:
            self.tasks = []

    def _save(self) -> None:
        """Save tasks to file."""
        data = {
            "tasks": [t.to_dict() for t in self.tasks],
            "next_id": self._next_id
        }
        with open(self.filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def add_task(self, title: str, description: str = "") -> Task:
        """Add a new task."""
        task = Task(
            id=self._next_id,
            title=title,
            description=description
        )
        self._next_id += 1
        self.tasks.append(task)
        self._save()
        return task

    def get_task(self, task_id: int) -> Optional[Task]:
        """Get task by ID."""
        return next((t for t in self.tasks if t.id == task_id), None)

    def complete_task(self, task_id: int) -> bool:
        """Mark task as completed."""
        task = self.get_task(task_id)
        if task:
            task.mark_completed()
            self._save()
            return True
        return False

    def delete_task(self, task_id: int) -> bool:
        """Delete a task."""
        original_len = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.id != task_id]
        if len(self.tasks) < original_len:
            self._save()
            return True
        return False

    def get_all_tasks(self) -> List[Task]:
        """Get all tasks."""
        return self.tasks

    def filter_tasks(self, status: Optional[str] = None, search: Optional[str] = None) -> List[Task]:
        """Filter tasks by status and/or search query."""
        result = self.tasks

        if status:
            result = [t for t in result if t.status == status]

        if search:
            search_lower = search.lower()
            result = [t for t in result if search_lower in t.title.lower() or
                     search_lower in t.description.lower()]

        return result


class TaskManager:
    """Main task manager CLI interface."""

    def __init__(self, storage: Optional[TaskStorage] = None):
        """Initialize task manager."""
        self.storage = storage or TaskStorage()

    def add(self, title: str, description: str = "") -> None:
        """Add a new task."""
        if not title.strip():
            print("Error: Task title cannot be empty", file=sys.stderr)
            sys.exit(1)

        task = self.storage.add_task(title.strip(), description.strip())
        print(f"✓ Added task #{task.id}: {task.title}")

    def complete(self, task_id: int) -> None:
        """Mark a task as completed."""
        if self.storage.complete_task(task_id):
            task = self.storage.get_task(task_id)
            print(f"✓ Completed: {task.title}")
        else:
            print(f"Error: Task #{task_id} not found", file=sys.stderr)
            sys.exit(1)

    def delete(self, task_id: int) -> None:
        """Delete a task."""
        task = self.storage.get_task(task_id)
        if not task:
            print(f"Error: Task #{task_id} not found", file=sys.stderr)
            sys.exit(1)

        if self.storage.delete_task(task_id):
            print(f"✓ Deleted: {task.title}")

    def list_tasks(self, status: Optional[str] = None, search: Optional[str] = None) -> None:
        """List tasks with optional filtering."""
        tasks = self.storage.filter_tasks(status=status, search=search)

        if not tasks:
            print("No tasks found.")
            return

        print(f"\n{'Tasks':<40} {'Status':<12} {'Created':<16}")
        print("─" * 68)

        for task in tasks:
            status_str = task.status.upper()
            created = datetime.fromisoformat(task.created_at).strftime("%Y-%m-%d %H:%M")
            print(f"#{task.id:<3} {task.title:<33} {status_str:<12} {created:<16}")
            if task.description:
                print(f"     └─ {task.description}")

        # Print summary
        completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED.value)
        pending = len(tasks) - completed
        print("─" * 68)
        print(f"Summary: {pending} pending, {completed} completed (total: {len(tasks)})")
        print()

    def show(self, task_id: int) -> None:
        """Show detailed information about a task."""
        task = self.storage.get_task(task_id)
        if not task:
            print(f"Error: Task #{task_id} not found", file=sys.stderr)
            sys.exit(1)

        print(task)
        if task.completed_at:
            completed = datetime.fromisoformat(task.completed_at).strftime("%Y-%m-%d %H:%M")
            print(f"Completed: {completed}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="A simple command-line task manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python task_manager.py add "Buy groceries" "Milk, eggs, bread"
  python task_manager.py list
  python task_manager.py list --status pending
  python task_manager.py list --search "groceries"
  python task_manager.py complete 1
  python task_manager.py show 1
  python task_manager.py delete 1
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new task")
    add_parser.add_argument("title", help="Task title")
    add_parser.add_argument("description", nargs="?", default="", help="Task description")

    # List command
    list_parser = subparsers.add_parser("list", help="List tasks")
    list_parser.add_argument("--status", choices=["pending", "completed"],
                            help="Filter by status")
    list_parser.add_argument("--search", help="Search in title and description")

    # Complete command
    complete_parser = subparsers.add_parser("complete", help="Mark task as completed")
    complete_parser.add_argument("task_id", type=int, help="Task ID")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a task")
    delete_parser.add_argument("task_id", type=int, help="Task ID")

    # Show command
    show_parser = subparsers.add_parser("show", help="Show task details")
    show_parser.add_argument("task_id", type=int, help="Task ID")

    args = parser.parse_args()
    manager = TaskManager()

    if args.command == "add":
        manager.add(args.title, args.description)
    elif args.command == "list":
        manager.list_tasks(status=args.status, search=args.search)
    elif args.command == "complete":
        manager.complete(args.task_id)
    elif args.command == "delete":
        manager.delete(args.task_id)
    elif args.command == "show":
        manager.show(args.task_id)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()