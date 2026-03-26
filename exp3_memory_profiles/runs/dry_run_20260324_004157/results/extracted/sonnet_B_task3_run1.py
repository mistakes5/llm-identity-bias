#!/usr/bin/env python3
"""
task_manager.py — A persistent command-line task manager.

Usage:
  python task_manager.py add "Buy groceries" --priority high --tags shopping,errands
  python task_manager.py list
  python task_manager.py list --status pending --priority high --tag shopping
  python task_manager.py done <id>
  python task_manager.py delete <id>
  python task_manager.py clear-done
"""

import argparse, json, os, sys, uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Literal, Optional


# ── ANSI colour helpers ────────────────────────────────────────────────────────

RESET  = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
RED    = "\033[91m"; GREEN = "\033[92m"; YELLOW = "\033[93m"; CYAN = "\033[96m"

def _no_color() -> bool:
    return not sys.stdout.isatty() or os.environ.get("NO_COLOR", "") != ""

def c(code: str, text: str) -> str:
    return text if _no_color() else f"{code}{text}{RESET}"


# ── Data model ─────────────────────────────────────────────────────────────────

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
PRIORITY_COLOR = {"high": RED, "medium": YELLOW, "low": GREEN}

@dataclass
class Task:
    title:        str
    id:           str           = field(default_factory=lambda: str(uuid.uuid4())[:8])
    status:       str           = "pending"    # "pending" | "done"
    priority:     str           = "medium"     # "high" | "medium" | "low"
    tags:         List[str]     = field(default_factory=list)
    created_at:   str           = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        return cls(**d)

    def render(self, index: int) -> str:
        num       = c(DIM,    f"[{index:>3}]")
        check     = c(GREEN,  "✓") if self.status == "done" else c(DIM, "○")
        title_txt = c(DIM,    self.title) if self.status == "done" else self.title
        pri       = c(PRIORITY_COLOR[self.priority], f"[{self.priority:<6}]")
        tags_txt  = c(CYAN,   "  #" + " #".join(self.tags)) if self.tags else ""
        date      = datetime.fromisoformat(self.completed_at or self.created_at).strftime("%b %d")
        return f"{num} {check} {pri} {title_txt}{tags_txt}  {c(DIM, date)}"


# ── Storage ────────────────────────────────────────────────────────────────────

DATA_DIR  = Path.home() / ".local" / "share" / "tasks"
DATA_FILE = DATA_DIR / "tasks.json"

def _load() -> List[Task]:
    if not DATA_FILE.exists():
        return []
    with DATA_FILE.open() as f:
        return [Task.from_dict(d) for d in json.load(f)]

def _save(tasks: List[Task]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with DATA_FILE.open("w") as f:
        json.dump([t.to_dict() for t in tasks], f, indent=2)


# ── Filtering — YOUR CODE GOES HERE ───────────────────────────────────────────

def filter_tasks(
    tasks:    List[Task],
    *,
    status:   Optional[str] = None,
    priority: Optional[str] = None,
    tag:      Optional[str] = None,
) -> List[Task]:
    """
    Return tasks matching ALL provided filters (AND logic).
    None means "no filter on this dimension".

    ┌─────────────────────────────────────────────────────────────────────┐
    │  TODO: implement this — 5-10 lines                                  │
    │                                                                     │
    │  Design decisions YOU get to make:                                  │
    │  • Case-sensitivity: should "Shopping" match tag "shopping"?        │
    │  • Partial match: does "shop" match tag "shopping"?                 │
    │  • All three filters are AND — a task must pass every active filter │
    └─────────────────────────────────────────────────────────────────────┘
    """
    raise NotImplementedError("Implement filter_tasks() above!")


def _sort(tasks: List[Task]) -> List[Task]:
    return sorted(tasks, key=lambda t: (
        0 if t.status == "pending" else 1,
        PRIORITY_ORDER[t.priority],
        t.created_at,
    ))


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_add(args):
    tasks = _load()
    tags  = [t.strip() for t in args.tags.split(",")] if args.tags else []
    task  = Task(title=args.title, priority=args.priority, tags=tags)
    tasks.append(task)
    _save(tasks)
    print(c(GREEN, "✓") + f" Added {c(BOLD, task.id)}: {task.title}")

def cmd_done(args):
    tasks   = _load()
    matches = [t for t in tasks if t.id.startswith(args.id) and t.status == "pending"]
    if not matches:
        print(c(RED, f"No pending task matching '{args.id}'.")); sys.exit(1)
    if len(matches) > 1:
        print(c(RED, f"Ambiguous ID — {len(matches)} matches. Use more characters.")); sys.exit(1)
    matches[0].status = "done"
    matches[0].completed_at = datetime.now().isoformat()
    _save(tasks)
    print(c(GREEN, "✓") + f" Done: {matches[0].title}")

def cmd_delete(args):
    tasks  = _load()
    before = len(tasks)
    tasks  = [t for t in tasks if not t.id.startswith(args.id)]
    if len(tasks) == before:
        print(c(RED, f"No task matching '{args.id}'.")); sys.exit(1)
    _save(tasks)
    print(c(YELLOW, "✗") + f" Deleted {args.id}.")

def cmd_clear_done(_args):
    tasks = _load()
    n     = sum(1 for t in tasks if t.status == "done")
    _save([t for t in tasks if t.status != "done"])
    print(c(YELLOW, f"Removed {n} completed task(s)."))

def cmd_list(args):
    tasks = _load()
    try:
        filtered = filter_tasks(
            tasks,
            status=args.status if args.status != "all" else None,
            priority=args.priority,
            tag=args.tag,
        )
    except NotImplementedError as e:
        print(c(RED, f"\n  ⚠  {e}\n")); sys.exit(1)

    rows = _sort(filtered)
    if not rows:
        print(c(DIM, "No tasks match your filters.")); return

    pending = sum(1 for t in tasks if t.status == "pending")
    print(c(BOLD, "\n  Tasks") + c(DIM, f"  ({pending} pending · {len(tasks)-pending} done · {len(tasks)} total)\n"))
    for i, t in enumerate(rows, 1):
        print("  " + t.render(i))
    print()


# ── CLI wiring ─────────────────────────────────────────────────────────────────

def build_parser():
    p = argparse.ArgumentParser(prog="task", description="Persistent CLI task manager.")
    sub = p.add_subparsers(dest="command", metavar="<command>")
    sub.required = True

    a = sub.add_parser("add", help="Add a task.")
    a.add_argument("title")
    a.add_argument("--priority", "-p", choices=["high","medium","low"], default="medium")
    a.add_argument("--tags", "-t", metavar="TAG[,TAG…]")
    a.set_defaults(func=cmd_add)

    d = sub.add_parser("done", help="Mark a task complete.")
    d.add_argument("id")
    d.set_defaults(func=cmd_done)

    r = sub.add_parser("delete", aliases=["rm"], help="Delete a task.")
    r.add_argument("id")
    r.set_defaults(func=cmd_delete)

    l = sub.add_parser("list", aliases=["ls"], help="List tasks.")
    l.add_argument("--status", "-s", choices=["pending","done","all"], default="all")
    l.add_argument("--priority", "-p", choices=["high","medium","low"], default=None)
    l.add_argument("--tag", "-t", default=None, metavar="TAG")
    l.set_defaults(func=cmd_list)

    c_ = sub.add_parser("clear-done", help="Remove all completed tasks.")
    c_.set_defaults(func=cmd_clear_done)

    return p

if __name__ == "__main__":
    build_parser().parse_args().func(build_parser().parse_args())

def filter_tasks(tasks, *, status=None, priority=None, tag=None):
    result = tasks
    if status   is not None: result = [t for t in result if ...]
    if priority is not None: result = [t for t in result if ...]
    if tag      is not None: result = [t for t in result if ...]
    return result