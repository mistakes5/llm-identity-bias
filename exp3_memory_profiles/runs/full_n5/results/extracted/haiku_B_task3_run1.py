#!/usr/bin/env python3
import json, argparse
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import List, Optional
import sys

TASKS_FILE = Path.home() / ".tasks.json"

@dataclass
class Task:
    id: int
    title: str
    description: str = ""
    status: str = "pending"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    due_date: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self): return asdict(self)
    @classmethod
    def from_dict(cls, data): return cls(**data)
    def mark_complete(self):
        self.status = "completed"
        self.completed_at = datetime.now().isoformat()
    def __str__(self):
        icon = "✓" if self.status == "completed" else "○"
        due = f" (due: {self.due_date})" if self.due_date else ""
        return f"[{icon}] #{self.id}: {self.title}{due}"

class TaskManager:
    def __init__(self, tasks_file=TASKS_FILE):
        self.tasks_file = tasks_file
        self.tasks = []
        self._load_tasks()

    def _load_tasks(self):
        if self.tasks_file.exists():
            try:
                with open(self.tasks_file) as f:
                    self.tasks = [Task.from_dict(t) for t in json.load(f)]
            except:
                self.tasks = []

    def _save_tasks(self):
        with open(self.tasks_file, "w") as f:
            json.dump([t.to_dict() for t in self.tasks], f, indent=2)

    def _next_id(self): return max((t.id for t in self.tasks), default=0) + 1
    def add_task(self, title, description="", due_date=None):
        task = Task(self._next_id(), title, description, due_date=due_date)
        self.tasks.append(task)
        self._save_tasks()
        return task
    def complete_task(self, tid):
        for t in self.tasks:
            if t.id == tid:
                t.mark_complete()
                self._save_tasks()
                return True
        return False
    def delete_task(self, tid):
        for i, t in enumerate(self.tasks):
            if t.id == tid:
                self.tasks.pop(i)
                self._save_tasks()
                return True
        return False
    def list_tasks(self, status=None): return [t for t in self.tasks if not status or t.status == status]
    def filter_tasks(self, **kwargs):
        r = self.tasks[:]
        if 'status' in kwargs: r = [t for t in r if t.status == kwargs['status']]
        if 'keyword' in kwargs:
            kw = kwargs['keyword'].lower()
            r = [t for t in r if kw in t.title.lower() or kw in t.description.lower()]
        if 'due_date' in kwargs: r = [t for t in r if t.due_date == kwargs['due_date']]
        return r
    def get_task(self, tid):
        for t in self.tasks:
            if t.id == tid: return t

def format_tasks(tasks, detailed=False):
    if not tasks: return "No tasks found."
    lines = []
    for t in tasks:
        lines.append(str(t))
        if detailed and t.description: lines.append(f"    Description: {t.description}")
        if detailed: lines.append(f"    Created: {t.created_at[:10]}")
    return "\n".join(lines)

def main():
    p = argparse.ArgumentParser(description="Task Manager CLI")
    s = p.add_subparsers(dest="cmd")
    ap = s.add_parser("add")
    ap.add_argument("title")
    ap.add_argument("--desc", default="")
    ap.add_argument("--due")
    cp = s.add_parser("complete")
    cp.add_argument("id", type=int)
    lp = s.add_parser("list")
    lp.add_argument("--status", choices=["pending","completed"])
    lp.add_argument("--detailed", action="store_true")
    fp = s.add_parser("filter")
    fp.add_argument("--status", choices=["pending","completed"])
    fp.add_argument("--keyword")
    fp.add_argument("--due")
    fp.add_argument("--detailed", action="store_true")
    dp = s.add_parser("delete")
    dp.add_argument("id", type=int)
    args = p.parse_args()
    m = TaskManager()
    if args.cmd == "add":
        t = m.add_task(args.title, args.desc, args.due)
        print(f"✓ Added: {t}")
    elif args.cmd == "complete":
        if m.complete_task(args.id): print(f"✓ Completed: {m.get_task(args.id)}")
        else: print(f"✗ Not found"); sys.exit(1)
    elif args.cmd == "list":
        print(format_tasks(m.list_tasks(args.status), args.detailed))
    elif args.cmd == "filter":
        f = {}
        if args.status: f["status"] = args.status
        if args.keyword: f["keyword"] = args.keyword
        if args.due: f["due_date"] = args.due
        print(format_tasks(m.filter_tasks(**f), args.detailed))
    elif args.cmd == "delete":
        if m.delete_task(args.id): print(f"✓ Deleted #{args.id}")
        else: print(f"✗ Not found"); sys.exit(1)
    else: p.print_help()

if __name__ == "__main__":
    main()