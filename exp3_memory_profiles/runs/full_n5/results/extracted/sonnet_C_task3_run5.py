#!/usr/bin/env python3
"""
tasks.py — A persistent command-line task manager.

Usage:
  python tasks.py add "Buy groceries" --priority high --tag shopping
  python tasks.py add "Write report" --due 2026-03-30 --tag work
  python tasks.py list
  python tasks.py list --status all --priority high
  python tasks.py list --tag work
  python tasks.py done 1
  python tasks.py delete 2
  python tasks.py show 3

Tasks are stored in ~/.tasks.json between sessions.
"""

import json
import argparse
import sys
from pathlib import Path
from datetime import datetime, date
from typing import Optional

# ── Storage ───────────────────────────────────────────────────────────────────

TASKS_FILE = Path.home() / ".tasks.json"

# ── ANSI colour helpers ───────────────────────────────────────────────────────

RESET  = "\033[0m"
BOLD   = "\033[1m"
DIM    = "\033[2m"
RED    = "\033[91m"
YELLOW = "\033[93m"
GREEN  = "\033[92m"
BLUE   = "\033[94m"
CYAN   = "\033[96m"
GRAY   = "\033[90m"

PRIORITY_COLOR = {"high": RED, "medium": YELLOW, "low": GREEN}
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}

# ── Persistence ───────────────────────────────────────────────────────────────

def load() -> dict:
    if TASKS_FILE.exists():
        try:
            with open(TASKS_FILE) as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            print(f"{RED}Warning: could not read {TASKS_FILE}: {exc}{RESET}", file=sys.stderr)
    return {"tasks": [], "next_id": 1}


def save(data: dict) -> None:
    """Atomically write via a temp file to avoid corruption on crash."""
    tmp = TASKS_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    tmp.replace(TASKS_FILE)


def find_task(data: dict, task_id: int) -> Optional[dict]:
    return next((t for t in data["tasks"] if t["id"] == task_id), None)

# ── Due-date display ──────────────────────────────────────────────────────────

def format_due(due_str: Optional[str]) -> str:
    """
    TODO — your turn! (~8 lines)

    Return a short coloured string for the due date column.

    Parameters
    ----------
    due_str : str | None
        ISO date "YYYY-MM-DD" stored on the task, or None.

    Colour constants available: RED, YELLOW, GREEN, CYAN, GRAY, RESET

    Ideas
    -----
    - delta = (due - date.today()).days
    - delta < 0  → overdue  → RED  + "overdue" or "Mar 20 !"
    - delta == 0 → today    → YELLOW + "today"
    - delta == 1 → tomorrow → CYAN   + "tomorrow"
    - delta > 1  → future   → CYAN   + "Apr 05"
    - None       → GRAY     + "—"
    """
    if due_str is None:
        return f"{GRAY}—{RESET}"

    try:
        due = date.fromisoformat(due_str)
    except ValueError:
        return due_str

    today = date.today()
    delta = (due - today).days

    # ── Replace the line below with your implementation ───────────────────
    return f"{CYAN}{due.strftime('%b %d')}{RESET}"
    # ─────────────────────────────────────────────────────────────────────

# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_add(args) -> None:
    data = load()
    task = {
        "id":           data["next_id"],
        "title":        args.title,
        "status":       "pending",
        "priority":     args.priority,
        "tags":         args.tags or [],
        "due":          args.due,
        "created_at":   datetime.now().isoformat(),
        "completed_at": None,
    }
    data["tasks"].append(task)
    data["next_id"] += 1
    save(data)
    p_color = PRIORITY_COLOR[task["priority"]]
    print(f"{GREEN}✓{RESET} Added task {BOLD}#{task['id']}{RESET}: {task['title']}  "
          f"[{p_color}{task['priority']}{RESET}]")


def cmd_done(args) -> None:
    data = load()
    task = find_task(data, args.id)
    if task is None:
        print(f"{RED}Task #{args.id} not found.{RESET}", file=sys.stderr); sys.exit(1)
    if task["status"] == "completed":
        print(f"Task #{args.id} is already completed."); return
    task["status"]       = "completed"
    task["completed_at"] = datetime.now().isoformat()
    save(data)
    print(f"{GREEN}✓{RESET} Completed task {BOLD}#{task['id']}{RESET}: {task['title']}")


def cmd_delete(args) -> None:
    data   = load()
    before = len(data["tasks"])
    data["tasks"] = [t for t in data["tasks"] if t["id"] != args.id]
    if len(data["tasks"]) == before:
        print(f"{RED}Task #{args.id} not found.{RESET}", file=sys.stderr); sys.exit(1)
    save(data)
    print(f"{RED}✕{RESET} Deleted task #{args.id}")


def cmd_list(args) -> None:
    data  = load()
    tasks = data["tasks"]

    if args.status != "all":
        tasks = [t for t in tasks if t["status"] == args.status]
    if args.priority:
        tasks = [t for t in tasks if t["priority"] == args.priority]
    if args.tag:
        tasks = [t for t in tasks if args.tag in t["tags"]]

    tasks = sorted(tasks, key=lambda t: (
        0 if t["status"] == "pending" else 1,
        PRIORITY_ORDER.get(t["priority"], 1),
        t["created_at"],
    ))

    if not tasks:
        print(f"{GRAY}No tasks match.{RESET}"); return

    print()
    print(f"{BOLD}{'#':<5} {'PRI':<8} {'TITLE':<42} {'TAGS':<20} {'DUE'}{RESET}")
    print(GRAY + "─" * 85 + RESET)

    for t in tasks:
        done     = t["status"] == "completed"
        dim      = DIM if done else ""
        check    = f"{GRAY}✓{RESET} " if done else "  "
        p_color  = PRIORITY_COLOR.get(t["priority"], "")
        title    = (t["title"][:37] + "...") if len(t["title"]) > 40 else t["title"]
        tags_str = ", ".join(t["tags"]) if t["tags"] else ""
        print(
            f"{dim}#{t['id']:<4} "
            f"{p_color}{t['priority']:<8}{RESET}{dim}"
            f"{check}{title:<40}  "
            f"{tags_str:<20}  "
            f"{format_due(t['due'])}{RESET}"
        )

    all_tasks = data["tasks"]
    pending   = sum(1 for t in all_tasks if t["status"] == "pending")
    print(f"\n{GRAY}{pending} pending · {len(all_tasks)-pending} completed · {len(all_tasks)} total{RESET}\n")


def cmd_show(args) -> None:
    data = load()
    task = find_task(data, args.id)
    if task is None:
        print(f"{RED}Task #{args.id} not found.{RESET}", file=sys.stderr); sys.exit(1)

    p_color = PRIORITY_COLOR.get(task["priority"], "")
    s_color = GREEN if task["status"] == "completed" else BLUE
    created = datetime.fromisoformat(task["created_at"]).strftime("%Y-%m-%d %H:%M")

    print(f"\n  {BOLD}Task #{task['id']}{RESET}")
    print(f"  {'Title':<12} {task['title']}")
    print(f"  {'Status':<12} {s_color}{task['status']}{RESET}")
    print(f"  {'Priority':<12} {p_color}{task['priority']}{RESET}")
    print(f"  {'Tags':<12} {', '.join(task['tags']) or GRAY + '—' + RESET}")
    print(f"  {'Due':<12} {format_due(task['due'])}")
    print(f"  {'Created':<12} {GRAY}{created}{RESET}")
    if task["completed_at"]:
        done_at = datetime.fromisoformat(task["completed_at"]).strftime("%Y-%m-%d %H:%M")
        print(f"  {'Completed':<12} {GRAY}{done_at}{RESET}")
    print()

# ── CLI wiring ────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tasks", description="Persistent command-line task manager")
    sub = p.add_subparsers(dest="command", required=True)

    a = sub.add_parser("add", help="Add a new task")
    a.add_argument("title")
    a.add_argument("--priority", choices=["low","medium","high"], default="medium")
    a.add_argument("--tag",      action="append", dest="tags",    metavar="TAG")
    a.add_argument("--due",      default=None,                    metavar="YYYY-MM-DD")

    d = sub.add_parser("done", help="Mark a task complete")
    d.add_argument("id", type=int)

    for alias in ("delete", "rm"):
        x = sub.add_parser(alias, help="Delete a task")
        x.add_argument("id", type=int)

    for alias in ("list", "ls"):
        l = sub.add_parser(alias, help="List and filter tasks")
        l.add_argument("--status",   choices=["pending","completed","all"], default="pending")
        l.add_argument("--priority", choices=["low","medium","high"],       default=None)
        l.add_argument("--tag",      default=None, metavar="TAG")

    s = sub.add_parser("show", help="Show full task details")
    s.add_argument("id", type=int)

    return p


def main() -> None:
    args = build_parser().parse_args()
    {
        "add": cmd_add, "done": cmd_done,
        "delete": cmd_delete, "rm": cmd_delete,
        "list": cmd_list,     "ls": cmd_list,
        "show": cmd_show,
    }[args.command](args)


if __name__ == "__main__":
    main()

today = date.today()
delta = (due - today).days

# your ~6 lines here — some possibilities:
# delta < 0  →  RED   "Mar 20 !" or just "overdue"
# delta == 0 →  YELLOW "today"
# delta == 1 →  CYAN   "tomorrow"
# delta > 1  →  CYAN   "Apr 05"