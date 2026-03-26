#!/usr/bin/env python3
import json, argparse, sys
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, field
from typing import List, Optional
from enum import Enum

class TaskStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"

@dataclass
class Task:
    id: int
    title: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    priority: str = "normal"
    tags: List[str] = field(default_factory=list)
    
    def to_dict(self):
        data = asdict(self)
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data):
        data['status'] = TaskStatus(data['status'])
        return cls(**data)

class TaskStorage:
    def __init__(self, storage_dir=None):
        self.storage_dir = Path(storage_dir) if storage_dir else Path.home() / '.task_manager'
        self.storage_file = self.storage_dir / 'tasks.json'
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def load_tasks(self):
        if not self.storage_file.exists():
            return []
        try:
            with open(self.storage_file) as f:
                return [Task.from_dict(t) for t in json.load(f)]
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Error loading: {e}", file=sys.stderr)
            return []
    
    def save_tasks(self, tasks):
        with open(self.storage_file, 'w') as f:
            json.dump([t.to_dict() for t in tasks], f, indent=2)

class TaskManager:
    def __init__(self, storage=None):
        self.storage = storage or TaskStorage()
        self.tasks = self.storage.load_tasks()
    
    def _get_next_id(self):
        return 1 if not self.tasks else max(t.id for t in self.tasks) + 1
    
    def add_task(self, title, priority="normal", tags=None):
        if not title.strip():
            raise ValueError("Title cannot be empty")
        task = Task(id=self._get_next_id(), title=title.strip(), priority=priority, tags=tags or [])
        self.tasks.append(task)
        self.storage.save_tasks(self.tasks)
        return task
    
    def complete_task(self, task_id):
        task = self.get_task_by_id(task_id)
        if task:
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now().isoformat()
            self.storage.save_tasks(self.tasks)
        return task
    
    def delete_task(self, task_id):
        self.tasks = [t for t in self.tasks if t.id != task_id]
        self.storage.save_tasks(self.tasks)
    
    def get_task_by_id(self, task_id):
        return next((t for t in self.tasks if t.id == task_id), None)
    
    def list_tasks(self):
        return self.tasks
    
    def filter_tasks(self, status=None, priority=None, tags=None, search=None):
        results = self.tasks
        if status:
            results = [t for t in results if t.status == status]
        if priority:
            results = [t for t in results if t.priority == priority]
        if tags:
            results = [t for t in results if any(tag in t.tags for tag in tags)]
        if search:
            results = [t for t in results if search.lower() in t.title.lower()]
        return results

def format_task(task, ts=False):
    symbol = "✓" if task.status == TaskStatus.COMPLETED else "○"
    priority_str = f" [{task.priority}]" if task.priority != "normal" else ""
    tags_str = f" #{', #'.join(task.tags)}" if task.tags else ""
    line = f"{symbol} [{task.id}] {task.title}{priority_str}{tags_str}"
    if ts:
        line += f"\n    Created: {task.created_at}"
        if task.completed_at:
            line += f" | Completed: {task.completed_at}"
    return line

def main():
    parser = argparse.ArgumentParser(description="Persistent task manager")
    sub = parser.add_subparsers(dest="cmd")
    
    # Add command
    add_cmd = sub.add_parser("add")
    add_cmd.add_argument("title")
    add_cmd.add_argument("--priority", default="normal", choices=["low", "normal", "high"])
    add_cmd.add_argument("--tags")
    
    # Complete command
    comp_cmd = sub.add_parser("complete")
    comp_cmd.add_argument("task_id", type=int)
    
    # Delete command
    del_cmd = sub.add_parser("delete")
    del_cmd.add_argument("task_id", type=int)
    
    # List command
    list_cmd = sub.add_parser("list")
    list_cmd.add_argument("--pending", action="store_true")
    list_cmd.add_argument("--completed", action="store_true")
    list_cmd.add_argument("--priority", choices=["low", "normal", "high"])
    list_cmd.add_argument("--tags")
    list_cmd.add_argument("--timestamps", action="store_true")
    
    # Search command
    search_cmd = sub.add_parser("search")
    search_cmd.add_argument("query")
    search_cmd.add_argument("--timestamps", action="store_true")
    
    args = parser.parse_args()
    mgr = TaskManager()
    
    if args.cmd == "add":
        tags = [t.strip() for t in args.tags.split(",")] if args.tags else []
        task = mgr.add_task(args.title, priority=args.priority, tags=tags)
        print(f"✓ Added task {task.id}: {task.title}")
    
    elif args.cmd == "complete":
        task = mgr.complete_task(args.task_id)
        if task:
            print(f"✓ Completed task {args.task_id}")
        else:
            print(f"✗ Task {args.task_id} not found")
            sys.exit(1)
    
    elif args.cmd == "delete":
        if mgr.get_task_by_id(args.task_id):
            mgr.delete_task(args.task_id)
            print(f"✓ Deleted task {args.task_id}")
        else:
            print(f"✗ Task {args.task_id} not found")
            sys.exit(1)
    
    elif not args.cmd or args.cmd == "list":
        status = None
        if getattr(args, "pending", False):
            status = TaskStatus.PENDING
        elif getattr(args, "completed", False):
            status = TaskStatus.COMPLETED
        
        priority = getattr(args, "priority", None)
        tags = [t.strip() for t in getattr(args, "tags", "").split(",")] if getattr(args, "tags", None) else None
        
        tasks = mgr.filter_tasks(status=status, priority=priority, tags=tags)
        if tasks:
            for task in tasks:
                print(format_task(task, getattr(args, "timestamps", False)))
            print(f"\n({len(tasks)} task{'s' if len(tasks) != 1 else ''})")
        else:
            print("No tasks found")
    
    elif args.cmd == "search":
        tasks = mgr.filter_tasks(search=args.query)
        if tasks:
            for task in tasks:
                print(format_task(task, args.timestamps))
            print(f"\n({len(tasks)} task{'s' if len(tasks) != 1 else ''})")
        else:
            print(f"No tasks found matching '{args.query}'")

if __name__ == "__main__":
    main()