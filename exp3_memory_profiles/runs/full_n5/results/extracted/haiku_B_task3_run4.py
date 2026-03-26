#!/usr/bin/env python3
import json, os, sys, uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List
import argparse

class Task:
    def __init__(self, title, description="", task_id=None, status="pending", 
                 created_date=None, completed_date=None):
        self.id = task_id or str(uuid.uuid4())[:8]
        self.title = title
        self.description = description
        self.status = status
        self.created_date = created_date or datetime.now().isoformat()
        self.completed_date = completed_date

    def to_dict(self):
        return {"id": self.id, "title": self.title, "description": self.description,
                "status": self.status, "created_date": self.created_date, 
                "completed_date": self.completed_date}

    @staticmethod
    def from_dict(data):
        return Task(**data)

    def mark_complete(self):
        self.status = "completed"
        self.completed_date = datetime.now().isoformat()

    def mark_pending(self):
        self.status = "pending"
        self.completed_date = None


class TaskManager:
    def __init__(self, data_dir=None):
        self.data_dir = Path(data_dir or "~/.task_manager").expanduser()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_file = self.data_dir / "tasks.json"
        self.tasks = self._load_tasks()

    def _load_tasks(self):
        if self.tasks_file.exists():
            try:
                with open(self.tasks_file) as f:
                    return [Task.from_dict(t) for t in json.load(f)]
            except: 
                return []
        return []

    def _save_tasks(self):
        with open(self.tasks_file, "w") as f:
            json.dump([t.to_dict() for t in self.tasks], f, indent=2)

    def add_task(self, title, description=""):
        if not title.strip(): 
            raise ValueError("Task title cannot be empty")
        task = Task(title, description)
        self.tasks.append(task)
        self._save_tasks()
        return task

    def list_tasks(self, status=None):
        if not status or status == "all":
            return self.tasks
        return [t for t in self.tasks if t.status == status]

    def complete_task(self, task_id):
        for t in self.tasks:
            if t.id == task_id:
                t.mark_complete()
                self._save_tasks()
                return t
        return None

    def pending_task(self, task_id):
        for t in self.tasks:
            if t.id == task_id:
                t.mark_pending()
                self._save_tasks()
                return t
        return None

    def delete_task(self, task_id):
        for i, t in enumerate(self.tasks):
            if t.id == task_id:
                self.tasks.pop(i)
                self._save_tasks()
                return t
        return None

    def search_tasks(self, keyword):
        kw = keyword.lower()
        return [t for t in self.tasks 
                if kw in t.title.lower() or kw in t.description.lower()]

    def clear_completed(self):
        original_len = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.status == "pending"]
        deleted_count = original_len - len(self.tasks)
        if deleted_count > 0:
            self._save_tasks()
        return deleted_count


class CLIFormatter:
    RESET = chr(27) + "[0m"
    GREEN = chr(27) + "[92m"
    YELLOW = chr(27) + "[93m"
    BLUE = chr(27) + "[94m"
    GRAY = chr(27) + "[90m"

    @staticmethod
    def _supports_color():
        return sys.stdout.isatty()

    @classmethod
    def _colorize(cls, text, color):
        if cls._supports_color():
            return color + text + cls.RESET
        return text

    @classmethod
    def format_task(cls, task):
        icon = "✓" if task.status == "completed" else "○"
        color = cls.GREEN if task.status == "completed" else cls.YELLOW
        status = cls._colorize(icon + " " + task.status, color)
        tid = cls._colorize("[" + task.id + "]", cls.BLUE)
        title = cls._colorize(task.title, cls.GRAY) if task.status == "completed" else task.title
        return status + " " + tid + " " + title

    @classmethod
    def format_task_list(cls, tasks):
        if not tasks:
            return cls._colorize("No tasks found.", cls.GRAY)
        
        lines = [cls.format_task(t) for t in tasks]
        pend = sum(1 for t in tasks if t.status == "pending")
        comp = sum(1 for t in tasks if t.status == "completed")
        summary = "\n" + cls._colorize("Summary:", cls.BLUE) + " " + str(pend) + " pending, " + str(comp) + " completed"
        return "\n".join(lines) + summary


def main():
    parser = argparse.ArgumentParser(description="Command-line Task Manager")
    parser.add_argument("command", nargs="?", default="list",
                       choices=["add","list","complete","pending","filter","delete","clear"],
                       help="Command to execute")
    parser.add_argument("arg", nargs="?", help="Argument for command")
    parser.add_argument("--description", "-d", default="", help="Task description")
    parser.add_argument("--status", "-s", choices=["pending","completed","all"],
                       help="Filter by status")
    parser.add_argument("--data-dir", help="Custom data directory")
    
    args = parser.parse_args()
    manager = TaskManager(data_dir=args.data_dir)
    formatter = CLIFormatter()

    if args.command == "add":
        if not args.arg:
            sys.exit("Error: Task title required")
        task = manager.add_task(args.arg, args.description)
        print("Task added: " + formatter.format_task(task))
        
    elif args.command == "list":
        tasks = manager.list_tasks(args.status)
        print(formatter.format_task_list(tasks))
        
    elif args.command == "complete":
        if not args.arg:
            sys.exit("Error: Task ID required")
        task = manager.complete_task(args.arg)
        if task:
            print("Task completed: " + formatter.format_task(task))
        else:
            print("Task not found")
            
    elif args.command == "pending":
        if not args.arg:
            sys.exit("Error: Task ID required")
        task = manager.pending_task(args.arg)
        if task:
            print("Task marked pending: " + formatter.format_task(task))
        else:
            print("Task not found")
            
    elif args.command == "filter":
        if not args.arg:
            sys.exit("Error: Search term required")
        tasks = manager.search_tasks(args.arg)
        print(formatter.format_task_list(tasks))
        
    elif args.command == "delete":
        if not args.arg:
            sys.exit("Error: Task ID required")
        task = manager.delete_task(args.arg)
        if task:
            print("Task deleted: " + formatter.format_task(task))
        else:
            print("Task not found")
            
    elif args.command == "clear":
        count = manager.clear_completed()
        if count > 0:
            print("Cleared " + str(count) + " completed task(s)")
        else:
            print("No completed tasks to clear")


if __name__ == "__main__":
    main()