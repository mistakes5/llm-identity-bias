#!/usr/bin/env python3
"""
Simple persistent task manager with CLI interface.
Tasks are stored in a JSON file and survive between sessions.
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
import argparse


class TaskManager:
    """Manages tasks with persistence."""

    def __init__(self, db_path: str = "tasks.json"):
        self.db_path = Path(db_path)
        self.tasks = self._load_tasks()

    def _load_tasks(self) -> list[dict]:
        """Load tasks from JSON file."""
        if self.db_path.exists():
            try:
                with open(self.db_path, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return []
        return []

    def _save_tasks(self) -> None:
        """Persist tasks to JSON file."""
        with open(self.db_path, 'w') as f:
            json.dump(self.tasks, f, indent=2)

    def add_task(self, title: str, description: str = "", tags: list[str] = None) -> int:
        """Add a new task. Returns task ID."""
        task_id = max((t.get('id', 0) for t in self.tasks), default=0) + 1

        task = {
            'id': task_id,
            'title': title,
            'description': description,
            'tags': tags or [],
            'completed': False,
            'created_at': datetime.now().isoformat(),
            'completed_at': None,
        }
        self.tasks.append(task)
        self._save_tasks()
        return task_id

    def complete_task(self, task_id: int) -> bool:
        """Mark a task as complete."""
        for task in self.tasks:
            if task['id'] == task_id:
                task['completed'] = True
                task['completed_at'] = datetime.now().isoformat()
                self._save_tasks()
                return True
        return False

    def delete_task(self, task_id: int) -> bool:
        """Delete a task."""
        for i, task in enumerate(self.tasks):
            if task['id'] == task_id:
                self.tasks.pop(i)
                self._save_tasks()
                return True
        return False

    def list_tasks(self, completed: Optional[bool] = None, tags: list[str] = None) -> list[dict]:
        """
        List tasks, optionally filtered by completion status and tags.

        Args:
            completed: If True/False, filter by completion status. If None, show all.
            tags: If provided, show only tasks that have at least one matching tag.

        Returns:
            Filtered list of tasks.
        """
        results = self.tasks

        if completed is not None:
            results = [t for t in results if t['completed'] == completed]

        if tags:
            results = [t for t in results if any(tag in t['tags'] for tag in tags)]

        return results

    def get_task(self, task_id: int) -> Optional[dict]:
        """Get a single task by ID."""
        for task in self.tasks:
            if task['id'] == task_id:
                return task
        return None


def format_task(task: dict, include_metadata: bool = False) -> str:
    """Format a task for display."""
    status = "✓" if task['completed'] else "○"
    tags_str = f" [{', '.join(task['tags'])}]" if task['tags'] else ""
    desc_str = f"\n    {task['description']}" if task['description'] else ""

    result = f"{status} [{task['id']}] {task['title']}{tags_str}{desc_str}"

    if include_metadata:
        created = datetime.fromisoformat(task['created_at']).strftime("%Y-%m-%d %H:%M")
        result += f"\n    Created: {created}"
        if task['completed_at']:
            completed = datetime.fromisoformat(task['completed_at']).strftime("%Y-%m-%d %H:%M")
            result += f" | Completed: {completed}"

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Simple persistent task manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python task_manager.py add "Buy groceries" --desc "Milk, eggs, bread" --tags shopping
  python task_manager.py list
  python task_manager.py list --pending
  python task_manager.py list --tags shopping
  python task_manager.py done 1
  python task_manager.py delete 2
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Add command
    add_parser = subparsers.add_parser('add', help='Add a new task')
    add_parser.add_argument('title', help='Task title')
    add_parser.add_argument('--desc', '--description', default='', help='Task description')
    add_parser.add_argument('--tags', nargs='+', default=[], help='Tags for the task')

    # List command
    list_parser = subparsers.add_parser('list', help='List tasks')
    list_parser.add_argument('--pending', action='store_true', help='Show only pending tasks')
    list_parser.add_argument('--completed', action='store_true', help='Show only completed tasks')
    list_parser.add_argument('--tags', nargs='+', default=[], help='Filter by tags')
    list_parser.add_argument('--verbose', '-v', action='store_true', help='Show creation/completion times')

    # Complete command
    complete_parser = subparsers.add_parser('done', help='Mark task as complete')
    complete_parser.add_argument('task_id', type=int, help='Task ID')

    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete a task')
    delete_parser.add_argument('task_id', type=int, help='Task ID')

    # Show command
    show_parser = subparsers.add_parser('show', help='Show task details')
    show_parser.add_argument('task_id', type=int, help='Task ID')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    tm = TaskManager()

    if args.command == 'add':
        task_id = tm.add_task(args.title, args.desc, args.tags)
        print(f"✓ Task {task_id} added: {args.title}")

    elif args.command == 'list':
        completed = None
        if args.pending:
            completed = False
        elif args.completed:
            completed = True

        tasks = tm.list_tasks(completed=completed, tags=args.tags)

        if not tasks:
            print("No tasks found.")
        else:
            for task in tasks:
                print(format_task(task, include_metadata=args.verbose))

    elif args.command == 'done':
        if tm.complete_task(args.task_id):
            print(f"✓ Task {args.task_id} marked complete.")
        else:
            print(f"✗ Task {args.task_id} not found.")

    elif args.command == 'delete':
        if tm.delete_task(args.task_id):
            print(f"✓ Task {args.task_id} deleted.")
        else:
            print(f"✗ Task {args.task_id} not found.")

    elif args.command == 'show':
        task = tm.get_task(args.task_id)
        if task:
            print(format_task(task, include_metadata=True))
        else:
            print(f"✗ Task {args.task_id} not found.")


if __name__ == '__main__':
    main()