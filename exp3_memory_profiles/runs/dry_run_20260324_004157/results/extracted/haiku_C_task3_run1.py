#!/usr/bin/env python3
import json, os, sys, argparse
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass, asdict

@dataclass
class Task:
    id: int
    title: str
    description: str = ""
    status: str = "pending"
    priority: str = "normal"
    created_date: str = None
    completed_date: Optional[str] = None

    def __post_init__(self):
        if self.created_date is None:
            self.created_date = datetime.now().isoformat()

    def mark_completed(self):
        self.status = "completed"
        self.completed_date = datetime.now().isoformat()

    def __str__(self):
        status_symbol = "✓" if self.status == "completed" else "○"
        priority_display = f"[{self.priority.upper()}]" if self.priority != "normal" else ""
        desc = f" — {self.description}" if self.description else ""
        return f"{status_symbol} #{self.id} {self.title} {priority_display}{desc}"

class TaskStorage:
    def __init__(self, filepath: str = None):
        if filepath is None:
            filepath = os.path.expanduser("~/.task_manager/tasks.json")
        self.filepath = Path(filepath)
        self.filepath.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> List[Task]:
        if not self.filepath.exists():
            return []
        try:
            with open(self.filepath) as f:
                data = json.load(f)
            return [Task(**task) for task in data]
        except json.JSONDecodeError:
            print(f"Warning: Could not parse {self.filepath}. Starting fresh.")
            return []

    def save(self, tasks: List[Task]):
        with open(self.filepath, "w") as f:
            json.dump([asdict(task) for task in tasks], f, indent=2)

class TaskManager:
    def __init__(self, storage: TaskStorage):
        self.storage = storage
        self.tasks = storage.load()

    def add(self, title: str, description: str = "", priority: str = "normal") -> Task:
        task_id = max([t.id for t in self.tasks], default=0) + 1
        task = Task(id=task_id, title=title, description=description, priority=priority)
        self.tasks.append(task)
        self.save()
        return task

    def complete(self, task_id: int) -> bool:
        for task in self.tasks:
            if task.id == task_id:
                task.mark_completed()
                self.save()
                return True
        return False

    def delete(self, task_id: int) -> bool:
        for i, task in enumerate(self.tasks):
            if task.id == task_id:
                self.tasks.pop(i)
                self.save()
                return True
        return False

    def list_all(self) -> List[Task]:
        return self.tasks

    def filter(self, status: Optional[str] = None, priority: Optional[str] = None) -> List[Task]:
        result = self.tasks
        if status:
            result = [t for t in result if t.status == status]
        if priority:
            result = [t for t in result if t.priority == priority]
        return result

    def search(self, query: str) -> List[Task]:
        query_lower = query.lower()
        return [t for t in self.tasks if query_lower in t.title.lower() or query_lower in t.description.lower()]

    def save(self):
        self.storage.save(self.tasks)

    def get_by_id(self, task_id: int) -> Optional[Task]:
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

class TaskManagerCLI:
    def __init__(self, manager: TaskManager):
        self.manager = manager

    def run(self):
        parser = argparse.ArgumentParser(description="CLI task manager", prog="task_manager")
        subparsers = parser.add_subparsers(dest="command", help="Commands")

        add_parser = subparsers.add_parser("add", help="Add a task")
        add_parser.add_argument("title", help="Task title")
        add_parser.add_argument("-d", "--description", default="", help="Description")
        add_parser.add_argument("-p", "--priority", choices=["low", "normal", "high"], default="normal")

        complete_parser = subparsers.add_parser("complete", help="Complete task")
        complete_parser.add_argument("task_id", type=int, help="Task ID")

        delete_parser = subparsers.add_parser("delete", help="Delete task")
        delete_parser.add_argument("task_id", type=int, help="Task ID")

        list_parser = subparsers.add_parser("list", help="List tasks")
        list_parser.add_argument("-s", "--status", choices=["pending", "completed"], help="Filter")
        list_parser.add_argument("-p", "--priority", choices=["low", "normal", "high"], help="Filter")

        search_parser = subparsers.add_parser("search", help="Search tasks")
        search_parser.add_argument("query", help="Search term")

        args = parser.parse_args()

        if not args.command:
            parser.print_help()
            return

        if args.command == "add":
            task = self.manager.add(title=args.title, description=args.description, priority=args.priority)
            print(f"Task added: {task}")
        elif args.command == "complete":
            if self.manager.complete(args.task_id):
                print(f"Task #{args.task_id} completed")
            else:
                print("Task not found")
                sys.exit(1)
        elif args.command == "delete":
            if self.manager.delete(args.task_id):
                print(f"Task #{args.task_id} deleted")
            else:
                print("Task not found")
                sys.exit(1)
        elif args.command == "list":
            tasks = self.manager.filter(status=args.status, priority=args.priority)
            if not tasks:
                print("No tasks")
                return
            pending = [t for t in tasks if t.status == "pending"]
            completed = [t for t in tasks if t.status == "completed"]
            if pending:
                print("Pending Tasks:")
                for task in pending:
                    print(f"  {task}")
            if completed:
                print("Completed Tasks:")
                for task in completed:
                    print(f"  {task}")
        elif args.command == "search":
            tasks = self.manager.search(args.query)
            if not tasks:
                print(f"No matches for {args.query}")
                return
            for task in tasks:
                print(f"  {task}")

def main():
    storage = TaskStorage()
    manager = TaskManager(storage)
    cli = TaskManagerCLI(manager)
    cli.run()

if __name__ == "__main__":
    main()