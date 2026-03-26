#!/usr/bin/env python3
"""
task.py — A persistent command-line task manager.

Usage:
  python task.py add "Buy groceries" [--priority high] [--due 2026-03-28] [--tags shopping,food]
  python task.py list [--status pending|done] [--priority low|medium|high] [--tag NAME] [--search TEXT]
  python task.py done <id>
  python task.py delete <id>
  python task.py show <id>
"""

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional
import uuid

# ── Storage location ───────────────────────────────────────────────────────────
TASKS_FILE = os.path.expanduser("~/.tasks.json")

# ── ANSI colors (auto-disabled when not a TTY or NO_COLOR is set) ──────────────
RESET  = "\033[0m";  BOLD   = "\033[1m";  DIM    = "\033[2m"
RED    = "\033[31m"; GREEN  = "\033[32m"; YELLOW = "\033[33m"; CYAN   = "\033[36m"

def _use_color() -> bool:
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")

def c(code: str, text: str) -> str:
    return f"{code}{text}{RESET}" if _use_color() else text

# ── Data model ─────────────────────────────────────────────────────────────────
PRIORITIES = ("low", "medium", "high")
STATUSES   = ("pending", "done")
PRIORITY_COLOR = {"low": DIM, "medium": RESET, "high": RED + BOLD}

@dataclass
class Task:
    id: str
    title: str
    status: str
    priority: str
    created_at: str
    due_date: Optional[str] = None
    tags: list = field(default_factory=list)
    completed_at: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        return cls(
            id=d["id"], title=d["title"],
            status=d.get("status", "pending"), priority=d.get("priority", "medium"),
            created_at=d["created_at"], due_date=d.get("due_date"),
            tags=d.get("tags", []), completed_at=d.get("completed_at"),
        )

    def is_overdue(self) -> bool:
        if self.status == "done" or not self.due_date:
            return False
        return self.due_date < datetime.now().strftime("%Y-%m-%d")

# ── Persistence ────────────────────────────────────────────────────────────────
def load_tasks() -> list:
    if not os.path.exists(TASKS_FILE):
        return []
    try:
        with open(TASKS_FILE, "r") as f:
            return [Task.from_dict(d) for d in json.load(f)]
    except (json.JSONDecodeError, KeyError) as exc:
        print(c(RED, f"  ✖ Could not read {TASKS_FILE}: {exc}"), file=sys.stderr)
        return []

def save_tasks(tasks: list) -> None:
    tmp = TASKS_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump([asdict(t) for t in tasks], f, indent=2)
    os.replace(tmp, TASKS_FILE)   # atomic on POSIX

# ── Core ───────────────────────────────────────────────────────────────────────
def create_task(title, priority="medium", due_date=None, tags=None) -> Task:
    return Task(
        id=uuid.uuid4().hex[:8], title=title, status="pending", priority=priority,
        created_at=datetime.now().isoformat(timespec="seconds"),
        due_date=due_date, tags=tags or [],
    )


def filter_tasks(tasks, *, status=None, priority=None, tag=None, search=None) -> list:
    """
    Filter tasks by one or more criteria (all filters are ANDed).

    Parameters:
        tasks    — full list from load_tasks()
        status   — "pending" or "done", or None to skip
        priority — "low", "medium", or "high", or None to skip
        tag      — match if this exact tag appears in task.tags
        search   — case-insensitive substring match on task.title

    Returns the filtered subset, preserving order.

    ── TODO: implement this function (5-10 lines) ──────────────────────────────
    Hint: start with `result = list(tasks)` then narrow with each filter:

        if status:    result = [t for t in result if t.status == status]
        if priority:  result = [t for t in result if t.priority == priority]
        if tag:       result = [t for t in result if tag in t.tags]
        if search:    result = [t for t in result if search.lower() in t.title.lower()]
        return result

    That gives AND logic. Feel free to try OR logic, fuzzy matching,
    or an `--overdue` filter via t.is_overdue() instead.
    ────────────────────────────────────────────────────────────────────────────
    """
    pass  # ← replace with your implementation


# ── Display ────────────────────────────────────────────────────────────────────
def _status_icon(t: Task) -> str:
    if t.status == "done":   return c(GREEN, "✓")
    if t.is_overdue():       return c(RED,   "!")
    return c(DIM, "○")

def _badge(p: str) -> str:
    return c(PRIORITY_COLOR.get(p, RESET), f"[{p[0].upper()}]")

def print_task_row(t: Task) -> None:
    due  = c(RED if t.is_overdue() and t.status != "done" else DIM, f"  due {t.due_date}") if t.due_date else ""
    tags = ("  " + c(CYAN, " ".join(f"#{tg}" for tg in t.tags))) if t.tags else ""
    title = c(DIM, t.title) if t.status == "done" else t.title
    print(f"  {_status_icon(t)}  {c(DIM, t.id)}  {_badge(t.priority)}  {title}{due}{tags}")

def print_task_detail(t: Task) -> None:
    print(f"\n  {c(BOLD, t.title)}")
    rows = [("ID", c(DIM, t.id)), ("Status", t.status),
            ("Priority", c(PRIORITY_COLOR.get(t.priority, RESET), t.priority)),
            ("Created", t.created_at)]
    if t.due_date:
        rows.append(("Due", c(RED if t.is_overdue() and t.status != "done" else RESET, t.due_date)))
    if t.tags:
        rows.append(("Tags", c(CYAN, ", ".join(t.tags))))
    if t.completed_at:
        rows.append(("Completed", t.completed_at))
    for label, value in rows:
        print(f"  {label:<14} {value}")
    print()

# ── Handlers ───────────────────────────────────────────────────────────────────
def cmd_add(args):
    tags = [t.strip() for t in args.tags.split(",")] if args.tags else []
    if args.due:
        try: datetime.strptime(args.due, "%Y-%m-%d")
        except ValueError:
            print(c(RED, "  ✖ Invalid due date — use YYYY-MM-DD"), file=sys.stderr); sys.exit(1)
    tasks = load_tasks()
    task  = create_task(args.title, priority=args.priority, due_date=args.due, tags=tags)
    tasks.append(task); save_tasks(tasks)
    print(f"  {c(GREEN, '+')} {c(BOLD, task.title)}  {c(DIM, task.id)}")

def cmd_list(args):
    tasks   = load_tasks()
    visible = filter_tasks(tasks, status=args.status, priority=args.priority,
                           tag=args.tag, search=args.search)
    if visible is None:
        print(c(RED, "  ✖ filter_tasks() returned None — implement it first!"), file=sys.stderr); sys.exit(1)
    if not visible:
        print(c(DIM, "  No matching tasks.")); return
    order = {"high": 0, "medium": 1, "low": 2}
    pending = sorted([t for t in visible if t.status == "pending"],
                     key=lambda x: (order.get(x.priority, 1), x.due_date or "9999"))
    done    = [t for t in visible if t.status == "done"]
    if pending:
        print(c(BOLD, f"\n  Pending ({len(pending)})"))
        for t in pending: print_task_row(t)
    if done:
        print(c(DIM, f"\n  Done ({len(done)})"))
        for t in done:    print_task_row(t)
    print()

def _find(tasks, prefix):
    m = [t for t in tasks if t.id.startswith(prefix)]
    if len(m) > 1:
        print(c(YELLOW, f"  Ambiguous '{prefix}' — {len(m)} matches. Use more characters."), file=sys.stderr); sys.exit(1)
    return m[0] if m else None

def cmd_done(args):
    tasks = load_tasks(); t = _find(tasks, args.id)
    if not t:   print(c(RED, f"  ✖ '{args.id}' not found."), file=sys.stderr); sys.exit(1)
    if t.status == "done": print(c(YELLOW, f"  Already done: {t.title}")); return
    t.status = "done"; t.completed_at = datetime.now().isoformat(timespec="seconds")
    save_tasks(tasks); print(f"  {c(GREEN, '✓')} {t.title}")

def cmd_delete(args):
    tasks = load_tasks(); t = _find(tasks, args.id)
    if not t:   print(c(RED, f"  ✖ '{args.id}' not found."), file=sys.stderr); sys.exit(1)
    save_tasks([x for x in tasks if x.id != t.id])
    print(f"  {c(RED, '×')} Deleted: {t.title}")

def cmd_show(args):
    tasks = load_tasks(); t = _find(tasks, args.id)
    if not t:   print(c(RED, f"  ✖ '{args.id}' not found."), file=sys.stderr); sys.exit(1)
    print_task_detail(t)

# ── Parser ─────────────────────────────────────────────────────────────────────
def build_parser():
    p = argparse.ArgumentParser(prog="task", description="A persistent CLI task manager.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="examples:\n  task add \"Write report\" --priority high --due 2026-03-28 --tags work\n  task list --status pending --tag work\n  task done a1b2c3\n  task delete a1b2")
    s = p.add_subparsers(dest="command", metavar="command"); s.required = True

    a = s.add_parser("add", help="Add a new task")
    a.add_argument("title"); a.add_argument("--priority", default="medium", choices=PRIORITIES)
    a.add_argument("--due", metavar="YYYY-MM-DD"); a.add_argument("--tags", metavar="TAG1,TAG2")
    a.set_defaults(func=cmd_add)

    l = s.add_parser("list", aliases=["ls"], help="List tasks")
    l.add_argument("--status", choices=STATUSES); l.add_argument("--priority", choices=PRIORITIES)
    l.add_argument("--tag", metavar="NAME"); l.add_argument("--search", metavar="TEXT")
    l.set_defaults(func=cmd_list)

    for name, aliases, handler, help_ in [
        ("done",   [],     cmd_done,   "Mark task complete"),
        ("delete", ["rm"], cmd_delete, "Delete a task"),
        ("show",   [],     cmd_show,   "Show task details"),
    ]:
        sub = s.add_parser(name, aliases=aliases, help=help_)
        sub.add_argument("id", help="Task ID (prefix OK)")
        sub.set_defaults(func=handler)

    return p

def main():
    args = build_parser().parse_args()
    args.func(args)

if __name__ == "__main__":
    main()

result = list(tasks)
if status:    result = [t for t in result if t.status == status]
if priority:  result = [t for t in result if t.priority == priority]
if tag:       result = [t for t in result if tag in t.tags]
if search:    result = [t for t in result if search.lower() in t.title.lower()]
return result