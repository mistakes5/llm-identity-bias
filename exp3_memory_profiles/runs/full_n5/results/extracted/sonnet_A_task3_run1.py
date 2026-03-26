#!/usr/bin/env python3
"""
taskman — a minimal, persistent command-line task manager.

Usage:
    python taskman.py add Buy milk --priority high --tags errands --due 2026-03-25
    python taskman.py list --status pending --tag errands
    python taskman.py done 3f2a
    python taskman.py remove 3f2a
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

# ── Storage ───────────────────────────────────────────────────────────────────

DATA_DIR  = Path.home() / ".local" / "share" / "taskman"
DATA_FILE = DATA_DIR / "tasks.json"

# ── ANSI colours ──────────────────────────────────────────────────────────────

RESET  = "\033[0m";  BOLD = "\033[1m";  DIM  = "\033[2m"
RED    = "\033[91m"; YELLOW = "\033[93m"; GREEN = "\033[92m"
GREY   = "\033[37m"; CYAN   = "\033[96m"

PRIORITY_COLOR: dict[str, str] = {"high": RED, "medium": YELLOW, "low": GREY}
PRIORITY_RANK:  dict[str, int] = {"high": 3,   "medium": 2,      "low": 1}


# ── Domain model ──────────────────────────────────────────────────────────────

@dataclass
class Task:
    title:        str
    priority:     str        = "medium"
    tags:         list[str]  = field(default_factory=list)
    due:          str | None = None       # YYYY-MM-DD or None
    status:       str        = "pending"  # "pending" | "done"
    id:           str        = field(default_factory=lambda: uuid.uuid4().hex[:8])
    created_at:   str        = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str | None = None

    @property
    def is_done(self) -> bool:
        return self.status == "done"

    @property
    def is_overdue(self) -> bool:
        if self.due and not self.is_done:
            return date.fromisoformat(self.due) < date.today()
        return False


# ── Persistence ───────────────────────────────────────────────────────────────

def load() -> list[Task]:
    if not DATA_FILE.exists():
        return []
    return [Task(**t) for t in json.loads(DATA_FILE.read_text())]

def save(tasks: list[Task]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps([asdict(t) for t in tasks], indent=2))


# ── Filtering & sorting ───────────────────────────────────────────────────────

def apply_filters(
    tasks:    list[Task],
    *,
    status:   str | None = None,
    priority: str | None = None,
    tag:      str | None = None,
    overdue:  bool       = False,
) -> list[Task]:
    """
    TODO — implement this function (see below).
    """
    pass   # ← replace with your implementation


# ── Rendering ─────────────────────────────────────────────────────────────────

def render_task(t: Task) -> None:
    symbol    = f"{GREEN}✓{RESET}" if t.is_done else "○"
    badge     = f"{PRIORITY_COLOR[t.priority]}[{t.priority[0].upper()}]{RESET}"
    title_fmt = f"{DIM}{t.title}{RESET}" if t.is_done else f"{BOLD}{t.title}{RESET}"

    due_str = ""
    if t.due:
        color, label = (RED, " ⚠ overdue") if t.is_overdue else (DIM, "")
        due_str = f"  {color}due {t.due}{label}{RESET}"

    tags_str = ("  " + " ".join(f"{CYAN}#{tg}{RESET}" for tg in t.tags)) if t.tags else ""
    print(f"  {DIM}{t.id}{RESET}  {symbol} {badge} {title_fmt}{due_str}{tags_str}")


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_add(args: argparse.Namespace) -> None:
    tasks = load()
    tags  = [t.strip() for t in args.tags.split(",")] if args.tags else []
    task  = Task(title=" ".join(args.title), priority=args.priority, tags=tags, due=args.due)
    tasks.append(task)
    save(tasks)
    pcol = PRIORITY_COLOR[task.priority]
    print(f"{GREEN}✓ Added{RESET}  {DIM}{task.id}{RESET}  {pcol}[{task.priority[0].upper()}]{RESET}  {BOLD}{task.title}{RESET}")

def cmd_done(args: argparse.Namespace) -> None:
    tasks   = load()
    matched = [t for t in tasks if t.id.startswith(args.id)]
    if not matched:
        print(f"{RED}Error: no task found with id prefix '{args.id}'{RESET}", file=sys.stderr); sys.exit(1)
    for t in matched:
        t.status = "done"; t.completed_at = datetime.now().isoformat()
        print(f"{GREEN}✓ Done{RESET}   {DIM}{t.id}{RESET}  {t.title}")
    save(tasks)

def cmd_remove(args: argparse.Namespace) -> None:
    tasks  = load(); before = len(tasks)
    tasks  = [t for t in tasks if not t.id.startswith(args.id)]
    if (removed := before - len(tasks)) == 0:
        print(f"{RED}Error: no task found with id prefix '{args.id}'{RESET}", file=sys.stderr); sys.exit(1)
    save(tasks); print(f"{RED}✗ Removed{RESET}  {removed} task(s).")

def cmd_list(args: argparse.Namespace) -> None:
    tasks    = load()
    filtered = apply_filters(tasks, status=args.status, priority=args.priority,
                             tag=args.tag, overdue=args.overdue)
    if filtered is None:
        print(f"{YELLOW}apply_filters() not yet implemented.{RESET}"); return
    if not filtered:
        print(f"{DIM}No tasks match your filters.{RESET}"); return
    print(f"\n  {BOLD}Tasks{RESET}  {DIM}({len(filtered)} of {len(tasks)} shown){RESET}\n")
    for t in filtered: render_task(t)
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="taskman", description="Persistent CLI task manager.")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("add", help="Add a task")
    a.add_argument("title", nargs="+"); a.add_argument("--priority", choices=["high","medium","low"], default="medium")
    a.add_argument("--tags"); a.add_argument("--due"); a.set_defaults(func=cmd_add)

    d = sub.add_parser("done", help="Mark task done"); d.add_argument("id"); d.set_defaults(func=cmd_done)
    r = sub.add_parser("remove", help="Delete a task"); r.add_argument("id"); r.set_defaults(func=cmd_remove)

    ls = sub.add_parser("list", help="List tasks")
    ls.add_argument("--status",   choices=["pending","done"])
    ls.add_argument("--priority", choices=["high","medium","low"])
    ls.add_argument("--tag"); ls.add_argument("--overdue", action="store_true")
    ls.set_defaults(func=cmd_list)

    return p

def main() -> None:
    args = build_parser().parse_args()
    args.func(args)

if __name__ == "__main__":
    main()

def apply_filters(tasks, *, status=None, priority=None, tag=None, overdue=False):
    result = tasks
    if status is not None:
        result = [t for t in result if t.status == status]
    if priority is not None:
        ...  # filter by priority
    if tag is not None:
        ...  # filter by tag — exact or substring?
    if overdue:
        ...  # filter to only t.is_overdue
    return sorted(result, key=lambda t: ...)