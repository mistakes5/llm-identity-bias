import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any


class Task:
    """Represents a single task."""

    def __init__(self, title: str, description: str = "", task_id: Optional[int] = None,
                 status: str = "pending", created_at: Optional[str] = None,
                 completed_at: Optional[str] = None):
        self.id = task_id
        self.title = title
        self.description = description
        self.status = status  # "pending" or "completed"
        self.created_at = created_at or datetime.now().isoformat()
        self.completed_at = completed_at

    def complete(self) -> None:
        """Mark task as completed."""
        self.status = "completed"
        self.completed_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary for JSON storage."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create Task from dictionary."""
        return cls(
            title=data["title"],
            description=data.get("description", ""),
            task_id=data["id"],
            status=data.get("status", "pending"),
            created_at=data.get("created_at"),
            completed_at=data.get("completed_at"),
        )

    def __repr__(self) -> str:
        status_symbol = "✓" if self.status == "completed" else "○"
        return f"[{status_symbol}] #{self.id}: {self.title}"


class TaskManager:
    """Manages task storage, retrieval, and operations."""

    def __init__(self, data_file: str = "tasks.json"):
        self.data_file = Path(data_file)
        self.tasks: Dict[int, Task] = {}
        self.next_id = 1
        self._load()

    def _load(self) -> None:
        """Load tasks from JSON file."""
        if self.data_file.exists():
            with open(self.data_file, "r") as f:
                data = json.load(f)
                for task_data in data:
                    task = Task.from_dict(task_data)
                    self.tasks[task.id] = task
                    self.next_id = max(self.next_id, task.id + 1)

    def _save(self) -> None:
        """Save tasks to JSON file."""
        data = [task.to_dict() for task in self.tasks.values()]
        with open(self.data_file, "w") as f:
            json.dump(data, f, indent=2)

    def add_task(self, title: str, description: str = "") -> Task:
        """Add a new task."""
        task = Task(title=title, description=description, task_id=self.next_id)
        self.tasks[self.next_id] = task
        self.next_id += 1
        self._save()
        return task

    def complete_task(self, task_id: int) -> Optional[Task]:
        """Mark a task as completed."""
        if task_id in self.tasks:
            self.tasks[task_id].complete()
            self._save()
            return self.tasks[task_id]
        return None

    def delete_task(self, task_id: int) -> bool:
        """Delete a task."""
        if task_id in self.tasks:
            del self.tasks[task_id]
            self._save()
            return True
        return False

    def get_task(self, task_id: int) -> Optional[Task]:
        """Get a specific task by ID."""
        return self.tasks.get(task_id)

    def get_all_tasks(self) -> List[Task]:
        """Get all tasks sorted by ID."""
        return sorted(self.tasks.values(), key=lambda t: t.id)

    def filter_tasks(self, status: Optional[str] = None,
                     search: Optional[str] = None) -> List[Task]:
        """
        Filter tasks by status and/or search term.

        Args:
            status: Filter by "pending" or "completed" (None = all)
            search: Search in title and description (case-insensitive)

        Returns:
            Filtered list of tasks
        """
        tasks = self.get_all_tasks()

        # Apply status filter
        if status:
            tasks = [t for t in tasks if t.status == status]

        # Apply search filter
        if search:
            search_lower = search.lower()
            tasks = [t for t in tasks 
                    if search_lower in t.title.lower() or 
                       search_lower in t.description.lower()]

        return tasks

import argparse
import sys
from task_manager import TaskManager


def main():
    parser = argparse.ArgumentParser(description="Simple task manager CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new task")
    add_parser.add_argument("title", help="Task title")
    add_parser.add_argument("-d", "--description", default="", help="Task description")

    # List command
    list_parser = subparsers.add_parser("list", help="List tasks")
    list_parser.add_argument("-s", "--status", choices=["pending", "completed"],
                            help="Filter by status")
    list_parser.add_argument("-q", "--query", help="Search in title and description")

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
        task = manager.add_task(args.title, args.description)
        print(f"✓ Created: {task}")

    elif args.command == "list":
        tasks = manager.filter_tasks(status=args.status, search=args.query)
        if not tasks:
            print("No tasks found.")
        else:
            for task in tasks:
                print(task)

    elif args.command == "complete":
        task = manager.complete_task(args.task_id)
        if task:
            print(f"✓ Completed: {task}")
        else:
            print(f"Task #{args.task_id} not found")
            sys.exit(1)

    elif args.command == "delete":
        if manager.delete_task(args.task_id):
            print(f"✓ Deleted task #{args.task_id}")
        else:
            print(f"Task #{args.task_id} not found")
            sys.exit(1)

    elif args.command == "show":
        task = manager.get_task(args.task_id)
        if task:
            print(f"{task}")
            if task.description:
                print(f"Description: {task.description}")
            print(f"Status: {task.status}")
            print(f"Created: {task.created_at}")
            if task.completed_at:
                print(f"Completed: {task.completed_at}")
        else:
            print(f"Task #{args.task_id} not found")
            sys.exit(1)

    else:
        parser.print_help()


if __name__ == "__main__":
    main()