#!/usr/bin/env python3
"""
Command-line task manager with persistent storage.
Tasks are stored as JSON and survive between sessions.
"""

import json
import os
from datetime import datetime
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional
import argparse


@dataclass
class Task:
    """Represents a single task."""
    id: int
    title: str
    completed: bool = False
    created_at: str = None
    completed_at: Optional[str] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

    def mark_complete(self):
        """Mark this task as completed."""
        self.completed = True
        self.completed_at = datetime.now().isoformat()

    def mark_incomplete(self):
        """Mark this task as incomplete."""
        self.completed = False
        self.completed_at = None

    def __str__(self):
        status = "✓" if self.completed else " "
        return f"[{status}] #{self.id}: {self.title}"


class TaskManager:
    """Manages task storage and operations."""

    def __init__(self, filepath: str = None):
        """Initialize with a storage file (default: ~/.task_manager.json)"""
        if filepath is None:
            filepath = os.path.expanduser("~/.task_manager.json")
        self.filepath = Path(filepath)
        self.tasks: List[Task] = []
        self.next_id = 1
        self._load()

    def _load(self):
        """Load tasks from JSON file."""
        if self.filepath.exists():
            try:
                with open(self.filepath, 'r') as f:
                    data = json.load(f)
                    self.tasks = [Task(**task_dict) for task_dict in data.get('tasks', [])]
                    self.next_id = data.get('next_id', 1)
            except (json.JSONDecodeError, ValueError):
                print(f"Warning: Could not load tasks from {self.filepath}")

    def _save(self):
        """Save tasks to JSON file."""
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'tasks': [asdict(task) for task in self.tasks],
            'next_id': self.next_id
        }
        with open(self.filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def add_task(self, title: str) -> Task:
        """Add a new task."""
        task = Task(id=self.next_id, title=title)
        self.next_id += 1
        self.tasks.append(task)
        self._save()
        return task

    def complete_task(self, task_id: int) -> bool:
        """Mark task as complete."""
        for task in self.tasks:
            if task.id == task_id:
                task.mark_complete()
                self._save()
                return True
        return False

    def uncomplete_task(self, task_id: int) -> bool:
        """Mark task as incomplete."""
        for task in self.tasks:
            if task.id == task_id:
                task.mark_incomplete()
                self._save()
                return True
        return False

    def delete_task(self, task_id: int) -> bool:
        """Delete a task."""
        original_length = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.id != task_id]
        if len(self.tasks) < original_length:
            self._save()
            return True
        return False

    def list_tasks(self, status: Optional[str] = None) -> List[Task]:
        """
        List tasks, optionally filtered.
        status: None (all), 'completed', or 'pending'
        """
        if status is None:
            return self.tasks
        elif status == 'completed':
            return [t for t in self.tasks if t.completed]
        elif status == 'pending':
            return [t for t in self.tasks if not t.completed]
        else:
            raise ValueError(f"Invalid status: {status}")

    def search_tasks(self, query: str) -> List[Task]:
        """Search tasks by title (case-insensitive)."""
        query_lower = query.lower()
        return [t for t in self.tasks if query_lower in t.title.lower()]


def main():
    """CLI interface."""
    parser = argparse.ArgumentParser(
        description="Command-line task manager with persistent storage"
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Add
    add_parser = subparsers.add_parser('add', help='Add a new task')
    add_parser.add_argument('title', nargs='+', help='Task title')

    # List
    list_parser = subparsers.add_parser('list', help='List tasks')
    list_parser.add_argument('--status', choices=['pending', 'completed'])

    # Complete
    complete_parser = subparsers.add_parser('complete', help='Mark task complete')
    complete_parser.add_argument('task_id', type=int, help='Task ID')

    # Uncomplete
    uncomplete_parser = subparsers.add_parser('uncomplete', help='Mark task incomplete')
    uncomplete_parser.add_argument('task_id', type=int, help='Task ID')

    # Delete
    delete_parser = subparsers.add_parser('delete', help='Delete a task')
    delete_parser.add_argument('task_id', type=int, help='Task ID')

    # Search
    search_parser = subparsers.add_parser('search', help='Search tasks')
    search_parser.add_argument('query', nargs='+', help='Search query')

    args = parser.parse_args()
    manager = TaskManager()

    if args.command == 'add':
        title = ' '.join(args.title)
        task = manager.add_task(title)
        print(f"Added: {task}")

    elif args.command == 'list':
        tasks = manager.list_tasks(status=args.status)
        if not tasks:
            print("No tasks found.")
        else:
            for task in tasks:
                print(task)

    elif args.command == 'complete':
        if manager.complete_task(args.task_id):
            print(f"Task #{args.task_id} marked complete.")
        else:
            print(f"Task #{args.task_id} not found.")

    elif args.command == 'uncomplete':
        if manager.uncomplete_task(args.task_id):
            print(f"Task #{args.task_id} marked incomplete.")
        else:
            print(f"Task #{args.task_id} not found.")

    elif args.command == 'delete':
        if manager.delete_task(args.task_id):
            print(f"Task #{args.task_id} deleted.")
        else:
            print(f"Task #{args.task_id} not found.")

    elif args.command == 'search':
        query = ' '.join(args.query)
        tasks = manager.search_tasks(query)
        if not tasks:
            print(f"No tasks matching '{query}'.")
        else:
            print(f"Found {len(tasks)}:")
            for task in tasks:
                print(task)

    else:
        parser.print_help()


if __name__ == '__main__':
    main()