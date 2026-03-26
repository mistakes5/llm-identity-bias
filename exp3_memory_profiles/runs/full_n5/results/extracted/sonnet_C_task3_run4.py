#!/usr/bin/env python3
"""
task_manager.py — A persistent command-line task manager.

Usage:
  python task_manager.py add Buy groceries --priority high --tags shopping food
  python task_manager.py list
  python task_manager.py list --status pending --priority high
  python task_manager.py list --tag shopping
  python task_manager.py complete 1
  python task_manager.py delete 3
"""

import json
import argparse
import sys
from pathlib import Path
from datetime import datetime

# ── Storage ───────────────────────────────────────────────────────────────────

TASKS_FILE = Path.home() / ".task_manager.json"

def load_tasks() -> dict:
    if TASKS_FILE.exists():
        with open(TASKS_FILE, "r") as f:
            return json.load(f)
    return {"tasks": [], "next_id": 1}

def save_tasks(data: dict) -> None:
    with open(TASKS_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_add(args, data):
    task = {
        "id": data["next_id"],
        "title": " ".join(args.title),
        "completed": False,
        "priority": args.priority,
        "tags": args.tags or [],
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
    }
    data["tasks"].append(task)
    data["next_id"] += 1
    save_tasks(data)
    print(f"✓  Added task #{task['id']}: {task['title']}  [{task['priority']}]")

def cmd_complete(args, data):
    for task in data["tasks"]:
        if task["id"] == args.id:
            if task["completed"]:
                print(f"Task #{args.id} is already completed.")
                return
            task["completed"] = True
            task["completed_at"] = datetime.now().isoformat()
            save_tasks(data)
            print(f"✓  Completed task #{args.id}: {task['title']}")
            return
    print(f"Error: Task #{args.id} not found.", file=sys.stderr)
    sys.exit(1)

def cmd_delete(args, data):
    before = len(data["tasks"])
    data["tasks"] = [t for t in data["tasks"] if t["id"] != args.id]
    if len(data["tasks"]) < before:
        save_tasks(data)
        print(f"✓  Deleted task #{args.id}.")
    else:
        print(f"Error: Task #{args.id} not found.", file=sys.stderr)
        sys.exit(1)

# ── Filtering — YOUR IMPLEMENTATION GOES HERE ─────────────────────────────────

def filter_tasks(tasks: list, status: str, tag: str | None, priority: str | None) -> list:
    """
    Filter tasks by status, tag, and priority.

    Parameters
    ----------
    tasks    : Full list of task dicts.
    status   : "pending" | "completed" | "all"
    tag      : Optional tag string — keep tasks whose 'tags' list contains it.
    priority : Optional priority string — keep tasks with this exact priority.

    Returns a new list matching ALL supplied criteria.

    TODO: Implement this function (5–10 lines).
    Hints:
      - Start with the full list and apply each filter one at a time.
      - status == "pending"   → task["completed"] is False
      - status == "completed" → task["completed"] is True
      - tag is None           → no tag filter; otherwise check tag in task["tags"]
      - priority is None      → no priority filter; otherwise exact match
    """
    # ── YOUR CODE HERE ────────────────────────────────────────────────────
    pass
    # ─────────────────────────────────────────────────────────────────────

# ── Display ───────────────────────────────────────────────────────────────────

_RED = "\033[91m"; _YELLOW = "\033[93m"; _GREEN = "\033[92m"
_DIM = "\033[2m";  _RESET  = "\033[0m"

PRIORITY_COLOR = {"high": _RED, "medium": _YELLOW, "low": _GREEN}
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}

def format_task(task: dict) -> str:
    icon   = "✓" if task["completed"] else "○"
    color  = PRIORITY_COLOR.get(task["priority"], "")
    tags   = f"  {_DIM}[{', '.join(task['tags'])}]{_RESET}" if task["tags"] else ""
    date   = task["created_at"][:10]
    dimmed = _DIM if task["completed"] else ""
    return (
        f"  {icon}  #{task['id']:>3}  "
        f"{color}{task['priority']:6}{_RESET}  "
        f"{dimmed}{task['title']}{_RESET}{tags}  {_DIM}({date}){_RESET}"
    )

def cmd_list(args, data):
    tasks = filter_tasks(data["tasks"], status=args.status, tag=args.tag, priority=args.priority)

    if tasks is None:
        print("\n⚠  filter_tasks() not implemented yet — open task_manager.py and fill in the TODO.\n")
        return
    if not tasks:
        print("No tasks match your filters.")
        return

    tasks = sorted(tasks, key=lambda t: (t["completed"], PRIORITY_ORDER.get(t["priority"], 1)))
    total   = len(data["tasks"])
    pending = sum(1 for t in data["tasks"] if not t["completed"])
    bar     = "─" * 62
    print(f"\n{bar}")
    print(f"  Tasks — {len(tasks)} shown  |  {pending} pending / {total} total")
    print(bar)
    for t in tasks:
        print(format_task(t))
    print(f"{bar}\n")

# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(prog="task", description="Persistent CLI task manager.")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("add", help="Add a task")
    a.add_argument("title", nargs="+")
    a.add_argument("--priority", "-p", choices=["high", "medium", "low"], default="medium")
    a.add_argument("--tags", "-t", nargs="*")

    for name, aliases in [("complete", ["done"]), ("delete", ["rm"])]:
        s = sub.add_parser(name, aliases=aliases)
        s.add_argument("id", type=int)

    ls = sub.add_parser("list", aliases=["ls"], help="List tasks")
    ls.add_argument("--status", "-s", choices=["pending", "completed", "all"], default="all")
    ls.add_argument("--tag")
    ls.add_argument("--priority", "-p", choices=["high", "medium", "low"])

    return p

def main():
    args = build_parser().parse_args()
    data = load_tasks()
    {
        "add": cmd_add, "complete": cmd_complete, "done": cmd_complete,
        "delete": cmd_delete, "rm": cmd_delete, "list": cmd_list, "ls": cmd_list,
    }[args.command](args, data)

if __name__ == "__main__":
    main()