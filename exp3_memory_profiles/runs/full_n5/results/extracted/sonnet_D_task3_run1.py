#!/usr/bin/env python3
"""
tasks.py — persistent CLI task manager

Commands:
  add  <title> [--priority low|medium|high] [--tag TAG ...]
  done <id>
  rm   <id>
  list [--status pending|done] [--priority low|medium|high] [--tag TAG]
"""

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Storage ────────────────────────────────────────────────────────────────────

STORE = Path.home() / ".tasks.json"

PRIORITIES = ("low", "medium", "high")
STATUSES   = ("pending", "done")

PRIORITY_COLOR = {"low": "\033[2m", "medium": "", "high": "\033[33m"}
RESET = "\033[0m"
DIM   = "\033[2m"
GREEN = "\033[32m"


# ── Model ──────────────────────────────────────────────────────────────────────

@dataclass
class Task:
    id:         int
    title:      str
    status:     str       = "pending"
    priority:   str       = "medium"
    tags:       list[str] = field(default_factory=list)
    created_at: str       = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )


# ── Persistence ────────────────────────────────────────────────────────────────

def load() -> list[Task]:
    if not STORE.exists():
        return []
    with STORE.open() as f:
        return [Task(**t) for t in json.load(f)]


def save(tasks: list[Task]) -> None:
    with STORE.open("w") as f:
        json.dump([asdict(t) for t in tasks], f, indent=2)


def next_id(tasks: list[Task]) -> int:
    return max((t.id for t in tasks), default=0) + 1


# ── Filtering ──────────────────────────────────────────────────────────────────

def matches(
    task:     Task,
    status:   Optional[str],
    priority: Optional[str],
    tag:      Optional[str],
) -> bool:
    """AND semantics: all non-None filters must match. Tag is exact, case-insensitive."""
    if status   and task.status   != status:                                  return False
    if priority and task.priority != priority:                                return False
    if tag      and tag.lower() not in [t.lower() for t in task.tags]:       return False
    return True


# ── Display ────────────────────────────────────────────────────────────────────

def fmt_task(task: Task) -> str:
    done  = f"{GREEN}✓{RESET}" if task.status == "done" else "○"
    color = PRIORITY_COLOR.get(task.priority, "")
    tags  = f"  {DIM}[{', '.join(task.tags)}]{RESET}" if task.tags else ""
    pri   = f"{color}{task.priority:<6}{RESET}"
    title = task.title if task.status == "pending" else f"{DIM}{task.title}{RESET}"
    return f"  {done} {task.id:>3}  {title:<50}  {pri}{tags}"


def print_tasks(tasks: list[Task]) -> None:
    if not tasks:
        print("  (no tasks)")
        return
    for t in tasks:
        print(fmt_task(t))


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_add(args: argparse.Namespace) -> None:
    tasks = load()
    task  = Task(
        id       = next_id(tasks),
        title    = args.title,
        priority = args.priority,
        tags     = args.tag or [],
    )
    tasks.append(task)
    save(tasks)
    print(f"Added #{task.id}: {task.title}")


def cmd_done(args: argparse.Namespace) -> None:
    tasks = load()
    for t in tasks:
        if t.id == args.id:
            if t.status == "done":
                print(f"#{args.id} already done.")
                return
            t.status = "done"
            save(tasks)
            print(f"Completed #{t.id}: {t.title}")
            return
    print(f"No task with id {args.id}.", file=sys.stderr)
    sys.exit(1)


def cmd_rm(args: argparse.Namespace) -> None:
    tasks     = load()
    remaining = [t for t in tasks if t.id != args.id]
    if len(remaining) == len(tasks):
        print(f"No task with id {args.id}.", file=sys.stderr)
        sys.exit(1)
    save(remaining)
    print(f"Removed #{args.id}.")


def cmd_list(args: argparse.Namespace) -> None:
    tasks   = load()
    visible = [t for t in tasks if matches(t, args.status, args.priority, args.tag)]

    pending = [t for t in visible if t.status == "pending"]
    done    = [t for t in visible if t.status == "done"]

    order = {p: i for i, p in enumerate(("high", "medium", "low"))}
    pending.sort(key=lambda t: order.get(t.priority, 99))
    done.sort(key=lambda t: t.created_at, reverse=True)

    if pending:
        print(f"\n  Pending ({len(pending)})")
        print_tasks(pending)

    if done and args.status != "pending":
        print(f"\n  Done ({len(done)})")
        print_tasks(done)

    if not visible:
        print("No matching tasks.")
    else:
        print()


# ── CLI ────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p   = argparse.ArgumentParser(prog="tasks", description="Persistent CLI task manager")
    sub = p.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="Add a task")
    add.add_argument("title")
    add.add_argument("--priority", "-p", default="medium", choices=PRIORITIES)
    add.add_argument("--tag", "-t", action="append", metavar="TAG")

    done = sub.add_parser("done", help="Mark complete")
    done.add_argument("id", type=int)

    rm = sub.add_parser("rm", help="Remove a task")
    rm.add_argument("id", type=int)

    ls = sub.add_parser("list", aliases=["ls"], help="List tasks")
    ls.add_argument("--status",   "-s", choices=STATUSES)
    ls.add_argument("--priority", "-p", choices=PRIORITIES)
    ls.add_argument("--tag",      "-t", metavar="TAG")

    return p


def main() -> None:
    dispatch = {"add": cmd_add, "done": cmd_done, "rm": cmd_rm, "list": cmd_list, "ls": cmd_list}
    args = build_parser().parse_args()
    dispatch[args.command](args)


if __name__ == "__main__":
    main()