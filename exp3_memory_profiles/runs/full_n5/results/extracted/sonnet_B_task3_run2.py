#!/usr/bin/env python3
"""
tasks.py — A minimal command-line task manager with persistent storage.

Storage: ~/.tasks/tasks.json

Usage examples:
    python tasks.py add "Write proposal" --priority high --due 2026-03-28 --tags work,urgent
    python tasks.py list
    python tasks.py list --all
    python tasks.py list --priority high --tag work
    python tasks.py complete 1
    python tasks.py edit 1 --priority low --due ''
    python tasks.py delete 2
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Optional

# ── ANSI colours (zero external deps) ────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
GREY   = "\033[90m"


def c(text: str, *codes: str) -> str:
    """Wrap text in ANSI codes. Always apply AFTER padding to avoid width issues."""
    return "".join(codes) + str(text) + RESET


# ── Data model ────────────────────────────────────────────────────────────────

PRIORITIES = ("high", "medium", "low")
STATUSES   = ("pending", "completed")


@dataclass
class Task:
    id: int
    title: str
    status: str = "pending"
    priority: str = "medium"
    tags: list[str] = field(default_factory=list)
    due: Optional[str] = None           # ISO date "YYYY-MM-DD"
    created_at: str = ""
    completed_at: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now().isoformat(timespec="seconds")

    @property
    def is_overdue(self) -> bool:
        return (
            self.due is not None
            and self.status == "pending"
            and date.fromisoformat(self.due) < date.today()
        )


# ── Sorting strategy ──────────────────────────────────────────────────────────

def sort_tasks(tasks: list[Task]) -> list[Task]:
    """
    Define the display order for `tasks list`.

    Default: priority (high → medium → low), overdue tasks bubble
    to the top within each group, then ascending ID as tiebreaker.

    ── Your turn ────────────────────────────────────────────────────
    Some alternatives to consider:

      • Soonest-due first (no-due-date tasks sink to bottom):
          key = (0 if t.due else 1, t.due or "9999", t.id)

      • Newest additions at the top (inbox/feed feel):
          key = (-t.id,)

      • Alphabetical by title within each priority group:
          key = (priority_order[t.priority], t.title.lower())

      • Completed tasks always last, regardless of priority:
          key = (1 if t.status == "completed" else 0,
                 priority_order[t.priority], t.id)
    ─────────────────────────────────────────────────────────────────
    """
    priority_order = {"high": 0, "medium": 1, "low": 2}

    def key(t: Task) -> tuple:
        overdue_first = 0 if t.is_overdue else 1
        return (priority_order[t.priority], overdue_first, t.id)

    return sorted(tasks, key=key)


# ── Persistence ───────────────────────────────────────────────────────────────

STORE_PATH = Path.home() / ".tasks" / "tasks.json"


def load_tasks() -> list[Task]:
    if not STORE_PATH.exists():
        return []
    raw = json.loads(STORE_PATH.read_text())
    return [Task(**t) for t in raw]


def save_tasks(tasks: list[Task]) -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STORE_PATH.write_text(json.dumps([asdict(t) for t in tasks], indent=2))


def next_id(tasks: list[Task]) -> int:
    return max((t.id for t in tasks), default=0) + 1


def find_task(tasks: list[Task], task_id: int) -> Optional[Task]:
    return next((t for t in tasks if t.id == task_id), None)


def validate_date(value: str) -> None:
    try:
        date.fromisoformat(value)
    except ValueError:
        die("Invalid date. Use YYYY-MM-DD format.")


# ── Display helpers ───────────────────────────────────────────────────────────

PRIORITY_COLOUR = {"high": RED, "medium": YELLOW, "low": BLUE}
PRIORITY_SYMBOL = {"high": "▲", "medium": "■", "low": "▼"}


def render_priority(p: str) -> str:
    return c(PRIORITY_SYMBOL[p], PRIORITY_COLOUR[p], BOLD)


def render_status(t: Task) -> str:
    return c("✓", GREEN, BOLD) if t.status == "completed" else c("○", GREY)


def truncate(text: str, width: int) -> str:
    return text[: width - 2] + ".." if len(text) > width else text


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_add(args: argparse.Namespace) -> None:
    tasks = load_tasks()
    if args.priority not in PRIORITIES:
        die(f"Invalid priority '{args.priority}'. Choose: {', '.join(PRIORITIES)}")
    if args.due:
        validate_date(args.due)

    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
    task = Task(id=next_id(tasks), title=args.title, priority=args.priority, tags=tags, due=args.due)
    tasks.append(task)
    save_tasks(tasks)

    extras = ""
    if task.tags: extras += f"  [{', '.join(task.tags)}]"
    if task.due:  extras += f"  due {task.due}"
    print(f"{c('✓', GREEN, BOLD)} Added {c(f'#{task.id}', BOLD, CYAN)}: {task.title}{c(extras, DIM)}")


def cmd_list(args: argparse.Namespace) -> None:
    tasks = load_tasks()

    if args.status:
        tasks = [t for t in tasks if t.status == args.status]
    elif not args.all:
        tasks = [t for t in tasks if t.status == "pending"]

    if args.priority:
        tasks = [t for t in tasks if t.priority == args.priority]
    if args.tag:
        tasks = [t for t in tasks if args.tag in t.tags]

    if not tasks:
        hint = "  (try --all to include completed tasks)" if not args.all else ""
        print(c(f"No tasks found.{hint}", DIM))
        return

    tasks = sort_tasks(tasks)

    W_ID = 5; W_TITLE = 42; W_PRI = 8; W_DUE = 14; W_TAGS = 22; SEP = "  "

    def hdr(text: str, w: int) -> str:
        return c(f"{text:<{w}}", BOLD, CYAN)

    print()
    print(hdr("ID", W_ID) + SEP + hdr("Title", W_TITLE) + SEP
          + hdr("Priority", W_PRI) + SEP + hdr("Due", W_DUE) + SEP + hdr("Tags", W_TAGS))
    print(c("─" * (W_ID + W_TITLE + W_PRI + W_DUE + W_TAGS + len(SEP) * 4), DIM))

    for t in tasks:
        id_col    = render_status(t) + " " + render_priority(t.priority) + " " + c(f"{t.id:<{W_ID-3}}", GREY)
        raw_title = truncate(t.title, W_TITLE)
        title_col = c(f"{raw_title:<{W_TITLE}}", DIM) if t.status == "completed" else f"{raw_title:<{W_TITLE}}"
        pri_col   = c(f"{t.priority:<{W_PRI}}", PRIORITY_COLOUR[t.priority])

        if t.due:
            suffix  = " !" if t.is_overdue else "   "
            due_col = c(f"{t.due + suffix:<{W_DUE}}", RED, BOLD) if t.is_overdue else c(f"{t.due + suffix:<{W_DUE}}", GREY)
        else:
            due_col = f"{'':<{W_DUE}}"

        tag_raw = truncate(", ".join(t.tags), W_TAGS) if t.tags else ""
        tag_col = c(f"{tag_raw:<{W_TAGS}}", GREY)

        print(id_col + SEP + title_col + SEP + pri_col + SEP + due_col + SEP + tag_col)

    total = len(tasks)
    print(c(f"\n{total} task{'s' if total != 1 else ''}", DIM))


def cmd_complete(args: argparse.Namespace) -> None:
    tasks = load_tasks()
    task  = find_task(tasks, args.id)
    if not task:
        die(f"Task #{args.id} not found.")
    if task.status == "completed":
        print(c(f"Task #{args.id} is already completed.", YELLOW)); return
    task.status       = "completed"
    task.completed_at = datetime.now().isoformat(timespec="seconds")
    save_tasks(tasks)
    print(f"{c('✓', GREEN, BOLD)} Completed {c(f'#{task.id}', BOLD, CYAN)}: {task.title}")


def cmd_delete(args: argparse.Namespace) -> None:
    tasks = load_tasks()
    task  = find_task(tasks, args.id)
    if not task:
        die(f"Task #{args.id} not found.")
    save_tasks([t for t in tasks if t.id != args.id])
    print(f"{c('✗', RED)} Deleted {c(f'#{args.id}', BOLD)}: {task.title}")


def cmd_edit(args: argparse.Namespace) -> None:
    tasks = load_tasks()
    task  = find_task(tasks, args.id)
    if not task:
        die(f"Task #{args.id} not found.")
    changed = False
    if args.title    is not None: task.title    = args.title;    changed = True
    if args.priority is not None:
        if args.priority not in PRIORITIES: die(f"Invalid priority. Choose: {', '.join(PRIORITIES)}")
        task.priority = args.priority; changed = True
    if args.tags is not None:
        task.tags = [t.strip() for t in args.tags.split(",") if t.strip()]; changed = True
    if args.due is not None:
        if args.due == "": task.due = None
        else: validate_date(args.due); task.due = args.due
        changed = True
    if not changed:
        print(c("Nothing changed — pass --title / --priority / --tags / --due.", YELLOW)); return
    save_tasks(tasks)
    print(f"{c('✎', BLUE)} Updated {c(f'#{task.id}', BOLD, CYAN)}: {task.title}")


# ── Error helper ──────────────────────────────────────────────────────────────

def die(msg: str) -> None:
    print(c(f"Error: {msg}", RED), file=sys.stderr)
    sys.exit(1)


# ── CLI wiring ────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="tasks",
        description="Minimal CLI task manager — persists to ~/.tasks/tasks.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  tasks add 'Write tests' --priority high --due 2026-03-28 --tags work\n"
            "  tasks list\n"
            "  tasks list --all\n"
            "  tasks list --priority high --tag work\n"
            "  tasks complete 1\n"
            "  tasks edit 1 --priority low --due ''\n"
            "  tasks delete 2\n"
        ),
    )
    sub = p.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="Add a new task")
    p_add.add_argument("title")
    p_add.add_argument("--priority", "-p", default="medium", choices=PRIORITIES)
    p_add.add_argument("--tags", "-t", metavar="TAG[,TAG]")
    p_add.add_argument("--due",  "-d", metavar="YYYY-MM-DD")

    p_list = sub.add_parser("list", aliases=["ls"], help="List tasks (pending by default)")
    p_list.add_argument("--all",      "-a", action="store_true")
    p_list.add_argument("--status",   "-s", choices=STATUSES)
    p_list.add_argument("--priority", "-p", choices=PRIORITIES)
    p_list.add_argument("--tag",      "-t", metavar="TAG")

    p_done = sub.add_parser("complete", aliases=["done", "check"], help="Mark task completed")
    p_done.add_argument("id", type=int)

    p_del = sub.add_parser("delete", aliases=["rm"], help="Delete a task")
    p_del.add_argument("id", type=int)

    p_edit = sub.add_parser("edit", help="Edit a task")
    p_edit.add_argument("id", type=int)
    p_edit.add_argument("--title")
    p_edit.add_argument("--priority", "-p", choices=PRIORITIES)
    p_edit.add_argument("--tags", "-t", metavar="TAG[,TAG]")
    p_edit.add_argument("--due",  "-d", metavar="YYYY-MM-DD", help="'' to clear")

    return p


DISPATCH: dict[str, object] = {
    "add": cmd_add, "list": cmd_list, "ls": cmd_list,
    "complete": cmd_complete, "done": cmd_complete, "check": cmd_complete,
    "delete": cmd_delete, "rm": cmd_delete, "edit": cmd_edit,
}


def main() -> None:
    args = build_parser().parse_args()
    handler = DISPATCH.get(args.command)
    if handler:
        handler(args)  # type: ignore[operator]
    else:
        build_parser().print_help()


if __name__ == "__main__":
    main()