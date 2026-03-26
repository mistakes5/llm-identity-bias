#!/usr/bin/env python3
"""
Command-line task manager with persistent storage.
Tasks are saved to JSON and survive between sessions.
"""

import json
import argparse
import sys
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
    """Represents a single task."""
    id: int
    title: str
    description: str = ""
    status: str = TaskStatus.PENDING.value
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    def mark_complete(self) -> None:
        """Mark task as completed."""
        self.status = TaskStatus.COMPLETED.value
        self.completed_at = datetime.now().isoformat()

    def mark_pending(self) -> None:
        """Mark task as pending."""
        self.status = TaskStatus.PENDING.value
        self.completed_at = None

    def __str__(self) -> str:
        status_icon = "✓" if self.status == TaskStatus.COMPLETED.value else "○"
        desc_str = f" — {self.description}" if self.description else ""
        return f"  [{status_icon}] #{self.id}: {self.title}{desc_str}"


class TaskManager:
    """Manages task persistence and operations."""

    def __init__(self, data_file: str = "~/.task_manager.json"):
        self.data_file = Path(data_file).expanduser()
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        self.tasks: List[Task] = []
        self.load()

    def load(self) -> None:
        """Load tasks from JSON file."""
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.tasks = [
                        Task(
                            id=t['id'],
                            title=t['title'],
                            description=t.get('description', ''),
                            status=t.get('status', TaskStatus.PENDING.value),
                            created_at=t.get('created_at', datetime.now().isoformat()),
                            completed_at=t.get('completed_at')
                        )
                        for t in data
                    ]
            except json.JSONDecodeError:
                print("Warning: Task file corrupted, starting fresh.", file=sys.stderr)
                self.tasks = []
        else:
            self.tasks = []

    def save(self) -> None:
        """Save tasks to JSON file."""
        with open(self.data_file, 'w') as f:
            json.dump([asdict(t) for t in self.tasks], f, indent=2)

    def add_task(self, title: str, description: str = "") -> Task:
        """Add a new task and return it."""
        task_id = max([t.id for t in self.tasks], default=0) + 1
        task = Task(id=task_id, title=title, description=description)
        self.tasks.append(task)
        self.save()
        return task

    def complete_task(self, task_id: int) -> bool:
        """Mark a task as completed. Returns True if successful."""
        for task in self.tasks:
            if task.id == task_id:
                task.mark_complete()
                self.save()
                return True
        return False

    def delete_task(self, task_id: int) -> bool:
        """Delete a task by ID. Returns True if successful."""
        original_len = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.id != task_id]
        if len(self.tasks) < original_len:
            self.save()
            return True
        return False

    def get_task(self, task_id: int) -> Optional[Task]:
        """Get a specific task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def filter_tasks(self, status: Optional[str] = None, query: Optional[str] = None) -> List[Task]:
        """
        Filter tasks by status and/or search query.

        TODO: Your turn! Implement this function.

        Parameters:
        - status: Filter by "pending" or "completed" (None = all statuses)
        - query: Search in title and description (case-insensitive substring match)

        Returns: List of matching tasks in original order

        Example behavior:
            manager.filter_tasks()  # all tasks
            manager.filter_tasks(status="pending")  # only pending
            manager.filter_tasks(query="buy")  # tasks with "buy" in title/desc
            manager.filter_tasks(status="completed", query="bug")  # both filters
        """
        # YOUR CODE HERE (5-10 lines)
        pass

    def list_tasks(self, status: Optional[str] = None, query: Optional[str] = None) -> None:
        """Display tasks in a formatted table."""
        filtered = self.filter_tasks(status=status, query=query)

        if not filtered:
            print("No tasks found.")
            return

        pending_count = sum(1 for t in filtered if t.status == TaskStatus.PENDING.value)
        completed_count = len(filtered) - pending_count

        print(f"\n📋 Tasks ({completed_count} done, {pending_count} pending):\n")
        for task in filtered:
            print(task)
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Simple task manager with persistent storage",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python task_manager.py add "Buy groceries"
  python task_manager.py add "Fix bug" -d "Issue #42 in auth module"
  python task_manager.py list
  python task_manager.py list -s pending
  python task_manager.py list -q "bug"
  python task_manager.py complete 1
  python task_manager.py delete 1
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to execute')

    # Add command
    add_parser = subparsers.add_parser('add', help='Add a new task')
    add_parser.add_argument('title', help='Task title')
    add_parser.add_argument('-d', '--description', default='', help='Task description')

    # Complete command
    complete_parser = subparsers.add_parser('complete', help='Mark a task as completed')
    complete_parser.add_argument('task_id', type=int, help='Task ID')

    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete a task')
    delete_parser.add_argument('task_id', type=int, help='Task ID')

    # List command
    list_parser = subparsers.add_parser('list', help='List tasks')
    list_parser.add_argument('-s', '--status', choices=['pending', 'completed'],
                            help='Filter by status')
    list_parser.add_argument('-q', '--query', help='Search in title/description')

    args = parser.parse_args()

    manager = TaskManager()

    if args.command == 'add':
        task = manager.add_task(args.title, args.description)
        print(f"✓ Added task #{task.id}: {task.title}")

    elif args.command == 'complete':
        if manager.complete_task(args.task_id):
            task = manager.get_task(args.task_id)
            print(f"✓ Completed: {task.title}")
        else:
            print(f"✗ Task #{args.task_id} not found.", file=sys.stderr)
            sys.exit(1)

    elif args.command == 'delete':
        if manager.delete_task(args.task_id):
            print(f"✓ Deleted task #{args.task_id}")
        else:
            print(f"✗ Task #{args.task_id} not found.", file=sys.stderr)
            sys.exit(1)

    elif args.command == 'list':
        manager.list_tasks(status=args.status, query=args.query)

    elif args.command is None:
        manager.list_tasks()
    else:
        parser.print_help()


if __name__ == '__main__':
    main()