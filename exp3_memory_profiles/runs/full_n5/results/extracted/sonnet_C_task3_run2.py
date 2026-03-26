#!/usr/bin/env python3
"""
tasks.py - A command-line task manager with persistence.
Tasks are saved to ~/.tasks.json between sessions.

Usage:
  python tasks.py add "Buy groceries" --priority high --tags shopping,errands
  python tasks.py list
  python tasks.py list --status all --priority high
  python tasks.py done 3
  python tasks.py filter --tag shopping --search "buy"
  python tasks.py delete 3
"""

import json, argparse, sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

TASKS_FILE = Path.home() / ".tasks.json"


# ── Data Model ────────────────────────────────────────────────────────────────

@dataclass
class Task:
    id: int
    title: str
    status: str = "pending"        # "pending" | "done"
    priority: str = "medium"       # "low" | "medium" | "high"
    tags: list = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    def to_dict(self):  return asdict(self)

    @classmethod
    def from_dict(cls, d):  return cls(**d)


# ── Storage ───────────────────────────────────────────────────────────────────

def load_tasks():
    if not TASKS_FILE.exists(): return []
    with TASKS_FILE.open() as f: data = json.load(f)
    return [Task.from_dict(t) for t in data]

def save_tasks(tasks):
    with TASKS_FILE.open("w") as f:
        json.dump([t.to_dict() for t in tasks], f, indent=2)

def next_id(tasks):
    return max((t.id for t in tasks), default=0) + 1


# ── Filtering ─────────────────────────────────────────────────────────────────

def filter_tasks(tasks, *, status=None, priority=None, tag=None, search=None):
    """
    Filter tasks by status, priority, tag, and/or search term.
    Each active filter narrows the results further (AND logic).

    TODO ── Implement filtering logic here (~5-10 lines).
    ─────────────────────────────────────────────────────────────────────────
    Hint: start with `result = list(tasks)` and progressively narrow it
    using list comprehensions for each active criterion.

    Design choices to consider:
      - Should `tag` use exact match or substring match?
      - If a task has multiple tags, does `tag` need to match just one
        of them, or all of them?
      - Should `search` also scan tags, or only the title?

    Each decision shapes how useful filtering feels day-to-day.
    ─────────────────────────────────────────────────────────────────────────
    """
    result = list(tasks)

    # ↓ Your filtering logic goes here (~5-10 lines)

    return result


# ── Display ───────────────────────────────────────────────────────────────────

PRIORITY_ORDER  = {"high": 0, "medium": 1, "low": 2}
PRIORITY_COLORS = {"high": "\033[91m", "medium": "\033[93m", "low": "\033[92m"}
RESET = "\033[0m";  DONE_COLOR = "\033[90m";  TAG_COLOR = "\033[36m"

def fmt_priority(p):
    return f"{PRIORITY_COLORS.get(p, '')}{p.upper()}{RESET}"

def fmt_tags(tags):
    return "  " + " ".join(f"{TAG_COLOR}#{t}{RESET}" for t in tags) if tags else ""

def print_tasks(tasks):
    if not tasks:
        print("  (no tasks found)"); return
    for t in sorted(tasks, key=lambda t: (t.status == "done", PRIORITY_ORDER.get(t.priority, 1), t.id)):
        check = "✓" if t.status == "done" else "○"
        color = DONE_COLOR if t.status == "done" else ""
        print(f"  {color}[{t.id:>3}] {check} {t.title}{RESET}  {fmt_priority(t.priority)}{fmt_tags(t.tags)}")


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_add(args, tasks):
    tags = [t.strip() for t in args.tags.split(",")] if args.tags else []
    task = Task(id=next_id(tasks), title=args.title, priority=args.priority, tags=tags)
    tasks.append(task);  save_tasks(tasks)
    print(f"  ✓ Added [{task.id}] {task.title}  {fmt_priority(task.priority)}")

def cmd_done(args, tasks):
    task = next((t for t in tasks if t.id == args.id), None)
    if not task: print(f"  ✗ No task with id {args.id}", file=sys.stderr); sys.exit(1)
    if task.status == "done": print(f"  Already completed: [{task.id}] {task.title}"); return
    task.status = "done";  task.completed_at = datetime.now().isoformat()
    save_tasks(tasks);  print(f"  ✓ Completed [{task.id}] {task.title}")

def cmd_list(args, tasks):
    status_f   = None if getattr(args, "status", "pending") == "all" else getattr(args, "status", "pending")
    filtered   = filter_tasks(tasks, status=status_f, priority=getattr(args, "priority", None),
                               tag=getattr(args, "tag", None), search=getattr(args, "search", None))
    print_tasks(filtered)

def cmd_delete(args, tasks):
    orig = len(tasks);  tasks[:] = [t for t in tasks if t.id != args.id]
    if len(tasks) == orig: print(f"  ✗ No task with id {args.id}", file=sys.stderr); sys.exit(1)
    save_tasks(tasks);  print(f"  ✓ Deleted task {args.id}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(prog="tasks", description="CLI task manager")
    sub = p.add_subparsers(dest="command", required=True)

    pa = sub.add_parser("add");     pa.add_argument("title")
    pa.add_argument("--priority", choices=["low","medium","high"], default="medium")
    pa.add_argument("--tags", help="Comma-separated, e.g. work,urgent")

    pd = sub.add_parser("done");    pd.add_argument("id", type=int)

    pl = sub.add_parser("list")
    pl.add_argument("--status", choices=["pending","done","all"], default="pending")
    pl.add_argument("--priority", choices=["low","medium","high"], default=None)
    pl.add_argument("--tag");       pl.add_argument("--search")

    pf = sub.add_parser("filter")   # same as list, but defaults to --status all
    pf.add_argument("--status", choices=["pending","done","all"], default="all")
    pf.add_argument("--priority", choices=["low","medium","high"], default=None)
    pf.add_argument("--tag");       pf.add_argument("--search")

    px = sub.add_parser("delete");  px.add_argument("id", type=int)
    return p

def main():
    args  = build_parser().parse_args()
    tasks = load_tasks()
    {"add": cmd_add, "done": cmd_done, "list": cmd_list,
     "filter": cmd_list, "delete": cmd_delete}[args.command](args, tasks)

if __name__ == "__main__":
    main()

# Option A — exact tag match (strict)
if tag:
    result = [t for t in result if tag in t.tags]

# Option B — partial tag match (fuzzy)
if tag:
    result = [t for t in result if any(tag in tg for tg in t.tags)]