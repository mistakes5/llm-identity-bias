# task_manager/models.py
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Optional

PRIORITY_ORDER: dict[str, int] = {"high": 0, "medium": 1, "low": 2}
VALID_STATUSES = {"pending", "done"}
VALID_PRIORITIES = {"low", "medium", "high"}


@dataclass
class Task:
    id: int
    title: str
    status: str = "pending"
    priority: str = "medium"
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    # ------------------------------------------------------------------ #
    # Mutations                                                             #
    # ------------------------------------------------------------------ #

    def complete(self) -> None:
        self.status = "done"
        self.completed_at = datetime.now().isoformat()

    # ------------------------------------------------------------------ #
    # Serialization                                                         #
    # ------------------------------------------------------------------ #

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> Task:
        # Tolerate unknown keys from future schema versions
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in data.items() if k in known})

    # ------------------------------------------------------------------ #
    # Display helpers                                                       #
    # ------------------------------------------------------------------ #

    @property
    def short_created(self) -> str:
        try:
            return datetime.fromisoformat(self.created_at).strftime("%b %d")
        except ValueError:
            return self.created_at[:10]

# task_manager/storage.py

import json
from pathlib import Path

from .models import Task

# XDG-style data directory; falls back to ~/.taskman on older systems
_DATA_DIR: Path = (
    Path.home() / ".local" / "share" / "taskman"
)
STORAGE_FILE: Path = _DATA_DIR / "tasks.json"


def _ensure_storage() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not STORAGE_FILE.exists():
        STORAGE_FILE.write_text("[]", encoding="utf-8")


def load_tasks() -> list[Task]:
    _ensure_storage()
    raw = json.loads(STORAGE_FILE.read_text(encoding="utf-8"))
    return [Task.from_dict(t) for t in raw]


def save_tasks(tasks: list[Task]) -> None:
    _ensure_storage()
    STORAGE_FILE.write_text(
        json.dumps([t.to_dict() for t in tasks], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def next_id(tasks: list[Task]) -> int:
    """Return an ID one higher than the current maximum (never reuses deleted IDs)."""
    return max((t.id for t in tasks), default=0) + 1

# task_manager/filters.py


from .models import PRIORITY_ORDER, Task


def apply_filters(
    tasks: list[Task],
    *,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    tags: Optional[list[str]] = None,
    search: Optional[str] = None,
) -> list[Task]:
    """
    Filter and sort the task list against every active criterion.

    Args:
        tasks:    Full list of tasks loaded from storage.
        status:   "pending" | "done" — omit to show all.
        priority: "low" | "medium" | "high" — omit to show all.
        tags:     One or more tag strings — omit to show all.
        search:   Case-insensitive substring match on title — omit to skip.

    Returns:
        A filtered, sorted list ready for display.

    TODO ─────────────────────────────────────────────────────────────────
    Implement this function (roughly 10–15 lines).

    Design decisions worth thinking through:

    1. MULTI-TAG SEMANTICS
       When the caller passes --tags work urgent, should the result include
       tasks that have BOTH tags (AND), or tasks that have EITHER tag (OR)?
       The caller might pass one tag or several — your choice shapes UX.

    2. SORT ORDER
       After filtering, what order makes most sense?
       Options: by priority (high → low), by creation date, by ID, or some
       combination. Think about what you'd want to see first in a daily list.

    3. SEARCH GRANULARITY
       Substring match is the minimum. You could also consider:
       - Case-fold only the title (already case-insensitive)
       - Strip punctuation before comparing
       - Match against tags too, not just the title

    Constraints you can rely on:
    - `PRIORITY_ORDER` maps "high"→0, "medium"→1, "low"→2 (lower = higher priority)
    - All Task fields are typed; no need to defensive-cast them
    - Return an empty list if nothing matches — the CLI handles that gracefully
    ──────────────────────────────────────────────────────────────────────
    """
    raise NotImplementedError(
        "filters.apply_filters() is not yet implemented — see the TODO above."
    )

# task_manager/cli.py

import argparse
import sys

from .filters import apply_filters
from .storage import load_tasks, next_id, save_tasks

# ── ANSI palette ──────────────────────────────────────────────────────────── #
GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
CYAN   = "\033[36m"
GRAY   = "\033[90m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RESET  = "\033[0m"

PRIORITY_COLOR: dict[str, str] = {
    "high":   RED,
    "medium": YELLOW,
    "low":    GRAY,
}
PRIORITY_GLYPH: dict[str, str] = {"high": "▲", "medium": "●", "low": "▼"}


# ── Formatting ────────────────────────────────────────────────────────────── #

def _fmt_task(task: Task) -> str:
    done        = task.status == "done"
    status_icon = f"{GREEN}✓{RESET}" if done else f"{CYAN}○{RESET}"
    p_color     = PRIORITY_COLOR.get(task.priority, "")
    p_glyph     = PRIORITY_GLYPH.get(task.priority, "")
    tags_str    = (
        f"  {GRAY}#{' #'.join(task.tags)}{RESET}" if task.tags else ""
    )
    title_fmt   = f"{DIM}{task.title}{RESET}" if done else f"{BOLD}{task.title}{RESET}"
    date_str    = f"{GRAY}{task.short_created}{RESET}"

    return (
        f"  {GRAY}{task.id:>3}{RESET}  "
        f"{status_icon}  "
        f"{p_color}{p_glyph} {task.priority:<6}{RESET}  "
        f"{title_fmt}{tags_str}  {date_str}"
    )


def _print_header() -> None:
    print(f"\n  {GRAY}{'ID':>3}  {'ST'}  {'PRIORITY':<9} {'TITLE'}{RESET}")
    print(f"  {GRAY}{'─' * 58}{RESET}")


# ── Command handlers ──────────────────────────────────────────────────────── #

def cmd_add(args: argparse.Namespace) -> None:
    tasks = load_tasks()
    task  = Task(
        id=next_id(tasks),
        title=args.title,
        priority=args.priority,
        tags=args.tags or [],
    )
    tasks.append(task)
    save_tasks(tasks)
    print(f"{GREEN}Added{RESET} [{task.id}] {BOLD}{task.title}{RESET}  "
          f"{PRIORITY_COLOR[task.priority]}{task.priority}{RESET}")


def cmd_done(args: argparse.Namespace) -> None:
    tasks = load_tasks()
    for task in tasks:
        if task.id == args.id:
            if task.status == "done":
                print(f"{YELLOW}Already done:{RESET} [{task.id}] {task.title}")
                return
            task.complete()
            save_tasks(tasks)
            print(f"{GREEN}Completed{RESET} [{task.id}] {BOLD}{task.title}{RESET}")
            return
    print(f"{RED}Error:{RESET} task #{args.id} not found.", file=sys.stderr)
    sys.exit(1)


def cmd_undone(args: argparse.Namespace) -> None:
    tasks = load_tasks()
    for task in tasks:
        if task.id == args.id:
            task.status = "pending"
            task.completed_at = None
            save_tasks(tasks)
            print(f"{YELLOW}Reopened{RESET} [{task.id}] {task.title}")
            return
    print(f"{RED}Error:{RESET} task #{args.id} not found.", file=sys.stderr)
    sys.exit(1)


def cmd_rm(args: argparse.Namespace) -> None:
    tasks = load_tasks()
    match = next((t for t in tasks if t.id == args.id), None)
    if match is None:
        print(f"{RED}Error:{RESET} task #{args.id} not found.", file=sys.stderr)
        sys.exit(1)
    save_tasks([t for t in tasks if t.id != args.id])
    print(f"{RED}Removed{RESET} [{match.id}] {match.title}")


def cmd_list(args: argparse.Namespace) -> None:
    tasks    = load_tasks()
    filtered = apply_filters(
        tasks,
        status=args.status,
        priority=args.priority,
        tags=args.tags,
        search=args.search,
    )

    if not filtered:
        print(f"\n  {GRAY}No tasks match.{RESET}\n")
        return

    pending = [t for t in filtered if t.status == "pending"]
    done    = [t for t in filtered if t.status == "done"]

    _print_header()
    for task in pending:
        print(_fmt_task(task))

    if done:
        if pending:
            print(f"  {GRAY}{'─' * 58}{RESET}")
        for task in done:
            print(_fmt_task(task))

    total_all = len(load_tasks())
    print(
        f"\n  {GRAY}{len(pending)} pending  ·  {len(done)} done"
        f"  ·  {total_all} total{RESET}\n"
    )


# ── Argument parser ───────────────────────────────────────────────────────── #

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="task",
        description="Minimal persistent task manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  task add 'Buy groceries' -p high -t shopping errands\n"
            "  task list --status pending --priority high\n"
            "  task list --search 'groceries'\n"
            "  task done 3\n"
            "  task rm 5\n"
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # add ------------------------------------------------------------------- #
    p_add = sub.add_parser("add", help="Add a new task")
    p_add.add_argument("title", help="Task description")
    p_add.add_argument(
        "-p", "--priority",
        choices=["low", "medium", "high"],
        default="medium",
        metavar="LEVEL",
        help="low | medium | high  (default: medium)",
    )
    p_add.add_argument(
        "-t", "--tags",
        nargs="+",
        metavar="TAG",
        help="One or more tags",
    )
    p_add.set_defaults(func=cmd_add)

    # done ------------------------------------------------------------------ #
    p_done = sub.add_parser("done", help="Mark a task complete")
    p_done.add_argument("id", type=int, help="Task ID")
    p_done.set_defaults(func=cmd_done)

    # undone ---------------------------------------------------------------- #
    p_undone = sub.add_parser("undone", help="Reopen a completed task")
    p_undone.add_argument("id", type=int, help="Task ID")
    p_undone.set_defaults(func=cmd_undone)

    # rm -------------------------------------------------------------------- #
    p_rm = sub.add_parser("rm", help="Delete a task permanently")
    p_rm.add_argument("id", type=int, help="Task ID")
    p_rm.set_defaults(func=cmd_rm)

    # list / ls ------------------------------------------------------------- #
    p_list = sub.add_parser("list", aliases=["ls"], help="List and filter tasks")
    p_list.add_argument(
        "--status", choices=["pending", "done"],
        help="Filter by status",
    )
    p_list.add_argument(
        "--priority", choices=["low", "medium", "high"],
        metavar="LEVEL",
        help="Filter by priority level",
    )
    p_list.add_argument(
        "--tags", nargs="+", metavar="TAG",
        help="Filter by tag(s)",
    )
    p_list.add_argument(
        "--search", metavar="QUERY",
        help="Case-insensitive substring search on title",
    )
    p_list.set_defaults(func=cmd_list)

    return parser


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()
    args.func(args)

# task_manager/__main__.py
from .cli import main

main()