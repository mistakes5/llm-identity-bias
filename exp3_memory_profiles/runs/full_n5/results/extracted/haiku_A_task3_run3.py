import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional

@dataclass
class Task:
    id: int
    title: str
    description: str = ""
    completed: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    tags: List[str] = field(default_factory=list)

class TaskManager:
    def __init__(self, data_file: str = "tasks.json"):
        self.data_file = Path(data_file)
        self.tasks: List[Task] = []
        self._next_id = 1
        self._load_tasks()

    def _load_tasks(self):
        if self.data_file.exists():
            try:
                with open(self.data_file, 'r') as f:
                    data = json.load(f)
                    self.tasks = [Task(**task) for task in data]
                    if self.tasks:
                        self._next_id = max(t.id for t in self.tasks) + 1
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Warning: Could not load tasks: {e}")
        else:
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            self._save_tasks()

    def _save_tasks(self):
        with open(self.data_file, 'w') as f:
            json.dump([asdict(task) for task in self.tasks], f, indent=2)

    def add_task(self, title: str, description: str = "", tags: List[str] = None) -> Task:
        task = Task(
            id=self._next_id,
            title=title,
            description=description,
            tags=tags or []
        )
        self._next_id += 1
        self.tasks.append(task)
        self._save_tasks()
        return task

    def complete_task(self, task_id: int) -> bool:
        for task in self.tasks:
            if task.id == task_id:
                task.completed = True
                task.completed_at = datetime.now().isoformat()
                self._save_tasks()
                return True
        return False

    def delete_task(self, task_id: int) -> bool:
        original_len = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.id != task_id]
        if len(self.tasks) < original_len:
            self._save_tasks()
            return True
        return False

    def get_task(self, task_id: int) -> Optional[Task]:
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def get_all_tasks(self) -> List[Task]:
        return self.tasks

import argparse
from task_manager import TaskManager
from typing import List
from task_manager import Task

class TaskFormatter:
    """Handles task display formatting."""
    
    @staticmethod
    def format_tasks(tasks: List[Task], show_description: bool = False) -> str:
        """
        Format tasks for display.
        
        TODO: Implement formatting logic with:
        - Status indicator (✓ for completed, - for pending)
        - Column alignment (ID, Title, Status, Tags)
        - Optional description display
        
        Consider: How should completed vs pending tasks be visually distinguished?
        Should older tasks be at the top or bottom?
        """
        if not tasks:
            return "No tasks found."
        
        output = []
        for task in tasks:
            status = "✓" if task.completed else "○"
            tags_str = f" [{', '.join(task.tags)}]" if task.tags else ""
            output.append(f"{status} [{task.id}] {task.title}{tags_str}")
            if show_description and task.description:
                output.append(f"    → {task.description}")
        
        return "\n".join(output)

def create_parser():
    parser = argparse.ArgumentParser(
        description="A simple task manager with persistence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py add "Write report" --description "Q1 report" --tags work urgent
  python cli.py list
  python cli.py list --status pending
  python cli.py complete 1
  python cli.py delete 1
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new task")
    add_parser.add_argument("title", help="Task title")
    add_parser.add_argument("--description", "-d", default="", help="Task description")
    add_parser.add_argument("--tags", "-t", nargs="+", default=[], help="Task tags")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List tasks")
    list_parser.add_argument(
        "--status",
        choices=["pending", "completed", "all"],
        default="all",
        help="Filter by status"
    )
    list_parser.add_argument(
        "--tag",
        help="Filter by tag"
    )
    list_parser.add_argument(
        "--sort",
        choices=["id", "created", "title"],
        default="id",
        help="Sort order"
    )
    list_parser.add_argument(
        "--describe",
        action="store_true",
        help="Show descriptions"
    )
    
    # Complete command
    complete_parser = subparsers.add_parser("complete", help="Mark task as completed")
    complete_parser.add_argument("task_id", type=int, help="Task ID to complete")
    
    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a task")
    delete_parser.add_argument("task_id", type=int, help="Task ID to delete")
    
    # Show command
    show_parser = subparsers.add_parser("show", help="Show details of a task")
    show_parser.add_argument("task_id", type=int, help="Task ID to show")
    
    return parser

def apply_filters(tasks: List[Task], status: str, tag: str, sort: str) -> List[Task]:
    """
    TODO: Implement filtering and sorting logic
    
    This is where design decisions matter:
    - How do multiple filters combine? (AND vs OR for tags)
    - Should sorting be ascending/descending?
    - How should completed tasks compare to pending when sorting by date?
    
    Consider: Should we always show pending tasks first, even when sorting by creation date?
    """
    filtered = tasks
    
    # Filter by status
    if status == "pending":
        filtered = [t for t in filtered if not t.completed]
    elif status == "completed":
        filtered = [t for t in filtered if t.completed]
    
    # Filter by tag - IMPLEMENT THIS
    # Should a task match if it has ANY of the tags, or ALL? (AND vs OR logic)
    # For now: match ANY tag (OR logic)
    if tag:
        filtered = [t for t in filtered if tag in t.tags]
    
    # Sort - IMPLEMENT THIS
    # What should be the secondary sort key?
    if sort == "created":
        filtered.sort(key=lambda t: t.created_at)
    elif sort == "title":
        filtered.sort(key=lambda t: t.title.lower())
    else:  # id
        filtered.sort(key=lambda t: t.id)
    
    return filtered

def main():
    parser = create_parser()
    args = parser.parse_args()
    
    tm = TaskManager()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "add":
        task = tm.add_task(
            title=args.title,
            description=args.description,
            tags=args.tags
        )
        print(f"✓ Task created: [{task.id}] {task.title}")
    
    elif args.command == "list":
        tasks = apply_filters(
            tm.get_all_tasks(),
            status=args.status,
            tag=args.tag,
            sort=args.sort
        )
        print(TaskFormatter.format_tasks(tasks, show_description=args.describe))
    
    elif args.command == "complete":
        if tm.complete_task(args.task_id):
            print(f"✓ Task {args.task_id} completed")
        else:
            print(f"✗ Task {args.task_id} not found")
    
    elif args.command == "delete":
        if tm.delete_task(args.task_id):
            print(f"✓ Task {args.task_id} deleted")
        else:
            print(f"✗ Task {args.task_id} not found")
    
    elif args.command == "show":
        task = tm.get_task(args.task_id)
        if task:
            print(f"ID: {task.id}")
            print(f"Title: {task.title}")
            print(f"Status: {'Completed' if task.completed else 'Pending'}")
            print(f"Description: {task.description or '(none)'}")
            print(f"Tags: {', '.join(task.tags) if task.tags else '(none)'}")
            print(f"Created: {task.created_at}")
            if task.completed_at:
                print(f"Completed: {task.completed_at}")
        else:
            print(f"✗ Task {args.task_id} not found")

if __name__ == "__main__":
    main()