#!/usr/bin/env python3
"""
tasks.py — A persistent command-line task manager.

Usage:
    python tasks.py add "Buy groceries" --priority high --tags shopping,errands
    python tasks.py list
    python tasks.py list --status pending --priority high
    python tasks.py list --tag shopping
    python tasks.py done <id>
    python tasks.py delete <id>
    python tasks.py clear --done
"""

import argparse
import json
import sys
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── Constants ────────────────────────────────────────────────────────────────

TASKS_FILE = Path.home() / ".tasks.json"
PRIORITIES = ("low", "medium", "high")
PRIORITY_COLORS = {"high": "\033[91m", "medium": "\033[93m", "low": "\033[94m"}
STATUS_COLORS = {"done": "\033[92m", "pending": "\033[0m"}
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"


# ── Data Model ───────────────────────────────────────────────────────────────

@dataclass
class Task:
    title: str
    priority: str = "medium"
    tags: list[str] = field(default_factory=list)
    status: str = "pending"
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    def __post_init__(self):
        if self.priority not in PRIORITIES:
            raise ValueError(f"Priority must be one of: {', '.join(PRIORITIES)}")
        if self.status not in ("pending", "done"):
            raise ValueError("Status must be 'pending' or 'done'")

    def complete(self):
        self.status = "done"
        self.completed_at = datetime.now().isoformat()

    def matches_filter(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> bool:
        if status and self.status != status:
            return False
        if priority and self.priority != priority:
            return False
        if tag and tag not in self.tags:
            return False
        return True

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(**data)


# ── Persistence ──────────────────────────────────────────────────────────────

def load_tasks() -> list[Task]:
    if not TASKS_FILE.exists():
        return []
    try:
        raw = json.loads(TASKS_FILE.read_text())
        return [Task.from_dict(t) for t in raw]
    except (json.JSONDecodeError, TypeError, KeyError) as e:
        print(f"⚠️  Warning: could not load tasks ({e}). Starting fresh.")
        return []


def save_tasks(tasks: list[Task]) -> None:
    TASKS_FILE.write_text(json.dumps([asdict(t) for t in tasks], indent=2))


# ── Formatting ───────────────────────────────────────────────────────────────

def fmt_priority(priority: str) -> str:
    color = PRIORITY_COLORS.get(priority, "")
    return f"{color}{priority:<6}{RESET}"


def fmt_status(status: str) -> str:
    if status == "done":
        return f"{STATUS_COLORS['done']}✔ done  {RESET}"
    return f"○ pending"


def fmt_tags(tags: list[str]) -> str:
    if not tags:
        return ""
    return f"{DIM}[{', '.join(tags)}]{RESET}"


def fmt_date(iso: Optional[str]) -> str:
    if not iso:
        return ""
    dt = datetime.fromisoformat(iso)
    return dt.strftime("%b %d %H:%M")


def print_tasks(tasks: list[Task]) -> None:
    if not tasks:
        print(f"{DIM}No tasks found.{RESET}")
        return

    # Header
    print(f"\n  {BOLD}{'ID':<10}{'STATUS':<12}{'PRI':<8}{'TITLE':<40}{'TAGS':<25}{'CREATED'}{RESET}")
    print(f"  {'─'*10}{'─'*12}{'─'*8}{'─'*40}{'─'*25}{'─'*16}")

    for task in tasks:
        title = task.title if len(task.title) <= 38 else task.title[:35] + "..."
        strike = "\033[9m" if task.status == "done" else ""
        row = (
            f"  {DIM}{task.id:<10}{RESET}"
            f"{fmt_status(task.status):<12}"
            f"{fmt_priority(task.priority):<8}"
            f"{strike}{title:<40}{RESET}"
            f"{fmt_tags(task.tags):<25}"
            f"{DIM}{fmt_date(task.created_at)}{RESET}"
        )
        print(row)

    pending = sum(1 for t in tasks if t.status == "pending")
    done = sum(1 for t in tasks if t.status == "done")
    print(f"\n  {DIM}{pending} pending · {done} done · {len(tasks)} total{RESET}\n")


# ── Commands ─────────────────────────────────────────────────────────────────

def cmd_add(args) -> None:
    tasks = load_tasks()
    tags = [t.strip() for t in args.tags.split(",")] if args.tags else []
    task = Task(title=args.title, priority=args.priority, tags=tags)
    tasks.append(task)
    save_tasks(tasks)
    print(f"✅ Added [{task.id}] {BOLD}{task.title}{RESET} ({fmt_priority(task.priority).strip()})")


def cmd_list(args) -> None:
    tasks = load_tasks()
    filtered = [
        t for t in tasks
        if t.matches_filter(
            status=args.status,
            priority=args.priority,
            tag=args.tag,
        )
    ]

    # Sort: pending before done, then by priority weight, then newest first
    priority_weight = {"high": 0, "medium": 1, "low": 2}
    filtered.sort(key=lambda t: (
        0 if t.status == "pending" else 1,
        priority_weight.get(t.priority, 1),
        t.created_at,
    ))

    print_tasks(filtered)


def cmd_done(args) -> None:
    tasks = load_tasks()
    matches = [t for t in tasks if t.id.startswith(args.id)]

    if not matches:
        print(f"❌ No task found with ID starting with '{args.id}'.")
        sys.exit(1)
    if len(matches) > 1:
        print(f"❌ Ambiguous ID '{args.id}' — matches {len(matches)} tasks. Be more specific.")
        sys.exit(1)

    task = matches[0]
    if task.status == "done":
        print(f"ℹ️  Task [{task.id}] is already done.")
        return

    task.complete()
    save_tasks(tasks)
    print(f"✔️  Completed [{task.id}] {BOLD}{task.title}{RESET}")


def cmd_delete(args) -> None:
    tasks = load_tasks()
    matches = [t for t in tasks if t.id.startswith(args.id)]

    if not matches:
        print(f"❌ No task found with ID starting with '{args.id}'.")
        sys.exit(1)
    if len(matches) > 1:
        print(f"❌ Ambiguous ID '{args.id}' — matches {len(matches)} tasks. Be more specific.")
        sys.exit(1)

    task = matches[0]
    tasks.remove(task)
    save_tasks(tasks)
    print(f"🗑️  Deleted [{task.id}] {task.title}")


def cmd_clear(args) -> None:
    tasks = load_tasks()
    if args.done:
        before = len(tasks)
        tasks = [t for t in tasks if t.status != "done"]
        removed = before - len(tasks)
        save_tasks(tasks)
        print(f"🧹 Removed {removed} completed task(s).")
    else:
        print("Specify --done to clear completed tasks, or --all to clear everything.")


# ── CLI Setup ─────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tasks",
        description="📋 A persistent command-line task manager.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", metavar="command")
    sub.required = True

    # add
    p_add = sub.add_parser("add", help="Add a new task")
    p_add.add_argument("title", help="Task description")
    p_add.add_argument(
        "--priority", "-p",
        choices=PRIORITIES,
        default="medium",
        help="Priority level (default: medium)",
    )
    p_add.add_argument(
        "--tags", "-t",
        help="Comma-separated tags, e.g. work,urgent",
    )
    p_add.set_defaults(func=cmd_add)

    # list
    p_list = sub.add_parser("list", aliases=["ls"], help="List tasks")
    p_list.add_argument("--status", "-s", choices=("pending", "done"), help="Filter by status")
    p_list.add_argument("--priority", "-p", choices=PRIORITIES, help="Filter by priority")
    p_list.add_argument("--tag", help="Filter by tag")
    p_list.set_defaults(func=cmd_list)

    # done
    p_done = sub.add_parser("done", help="Mark a task as complete")
    p_done.add_argument("id", help="Task ID (or unique prefix)")
    p_done.set_defaults(func=cmd_done)

    # delete
    p_del = sub.add_parser("delete", aliases=["rm"], help="Delete a task")
    p_del.add_argument("id", help="Task ID (or unique prefix)")
    p_del.set_defaults(func=cmd_delete)

    # clear
    p_clear = sub.add_parser("clear", help="Bulk-remove tasks")
    p_clear.add_argument("--done", action="store_true", help="Remove all completed tasks")
    p_clear.set_defaults(func=cmd_clear)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except ValueError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()