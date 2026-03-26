#!/usr/bin/env python3
import json, os, argparse
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Optional, List
from enum import Enum

class TaskStatus(Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    ARCHIVED = "archived"

@dataclass
class Task:
    id: int
    title: str
    description: str = ""
    status: str = TaskStatus.PENDING.value
    priority: str = "normal"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None
    def to_dict(self): return asdict(self)
    @staticmethod
    def from_dict(d): return Task(**d)

class TaskManager:
    def __init__(self, data_dir: Optional[str] = None):
        if not data_dir: data_dir = os.path.expanduser("~/.task_manager")
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_file = self.data_dir / "tasks.json"
        self.tasks = []
        self._load_tasks()
    def _load_tasks(self):
        if self.tasks_file.exists():
            try:
                with open(self.tasks_file) as f:
                    self.tasks = [Task.from_dict(i) for i in json.load(f)]
            except: pass
    def _save_tasks(self):
        try:
            with open(self.tasks_file, "w") as f:
                json.dump([t.to_dict() for t in self.tasks], f, indent=2)
        except: pass
    def _get_next_id(self): return max((t.id for t in self.tasks), default=0) + 1
    def add_task(self, title, description="", priority="normal"):
        if not title.strip(): raise ValueError("Task title cannot be empty")
        t = Task(id=self._get_next_id(), title=title, description=description, priority=priority)
        self.tasks.append(t)
        self._save_tasks()
        return t
    def complete_task(self, task_id):
        for t in self.tasks:
            if t.id == task_id:
                t.status = TaskStatus.COMPLETED.value
                t.completed_at = datetime.now().isoformat()
                self._save_tasks()
                return t
    def delete_task(self, task_id):
        before = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.id != task_id]
        if len(self.tasks) < before: self._save_tasks(); return True
    def list_tasks(self, status=None, priority=None):
        r = self.tasks
        if status: r = [t for t in r if t.status == status]
        if priority: r = [t for t in r if t.priority == priority]
        return r
    def get_task(self, task_id):
        for t in self.tasks:
            if t.id == task_id: return t

def format_task(t, verbose=False):
    e = chr(10003) if t.status == TaskStatus.COMPLETED.value else chr(9675)
    p = t.priority[0].upper()
    o = f"{e} [{t.id:3d}] {t.title:<40} [{p}]"
    if verbose:
        o += f"\n    Status: {t.status}\n    Priority: {t.priority}"
        if t.description: o += f"\n    Desc: {t.description}"
        o += f"\n    Created: {t.created_at}"
        if t.completed_at: o += f"\n    Done: {t.completed_at}"
    return o

def main():
    p = argparse.ArgumentParser(description="Task Manager")
    s = p.add_subparsers(dest="command")
    ap = s.add_parser("add")
    ap.add_argument("title")
    ap.add_argument("-d", "--description", default="")
    ap.add_argument("-p", "--priority", choices=["low", "normal", "high"], default="normal")
    cp = s.add_parser("complete")
    cp.add_argument("task_id", type=int)
    dp = s.add_parser("delete")
    dp.add_argument("task_id", type=int)
    lp = s.add_parser("list")
    lp.add_argument("-s", "--status", choices=["pending", "completed", "archived"])
    lp.add_argument("-p", "--priority", choices=["low", "normal", "high"])
    lp.add_argument("-v", "--verbose", action="store_true")
    sp = s.add_parser("show")
    sp.add_argument("task_id", type=int)
    a = p.parse_args()
    m = TaskManager()
    if a.command == "add":
        try:
            t = m.add_task(title=a.title, description=a.description, priority=a.priority)
            print(f"✓ Created: {format_task(t)}")
        except ValueError as e:
            print(f"✗ Error: {e}")
    elif a.command == "complete":
        t = m.complete_task(a.task_id)
        print(f"✓ Done: {format_task(t)}" if t else f"✗ Not found")
    elif a.command == "delete":
        print(f"✓ Deleted" if m.delete_task(a.task_id) else f"✗ Not found")
    elif a.command == "list":
        tasks = m.list_tasks(status=a.status, priority=a.priority)
        if not tasks: print("No tasks")
        else:
            print(f"Total: {len(tasks)}")
            for t in tasks: print(format_task(t, verbose=a.verbose))
    elif a.command == "show":
        t = m.get_task(a.task_id)
        print(format_task(t, verbose=True) if t else f"✗ Not found")
    else:
        p.print_help()

if __name__ == "__main__": main()