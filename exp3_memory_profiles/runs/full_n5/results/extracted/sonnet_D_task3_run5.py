#!/usr/bin/env python3
"""tasks — persistent CLI task manager

Usage:
  tasks add 'Fix the ingestion pipeline' --tag etl --tag urgent
  tasks ls
  tasks ls --status all --tag etl
  tasks ls --search pipeline
  tasks done abc123
  tasks rm  abc123
"""

import json
import sys
import uuid
from argparse import ArgumentParser, RawDescriptionHelpFormatter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

STORE = Path.home() / ".tasks.json"
DATE_FMT = "%Y-%m-%d %H:%M"


@dataclass
class Task:
    id: str
    title: str
    status: str = "pending"          # "pending" | "done"
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: _now())
    completed_at: Optional[str] = None


def _now() -> str:
    return datetime.now(timezone.utc).strftime(DATE_FMT)


def load() -> list[Task]:
    if not STORE.exists():
        return []
    try:
        data = json.loads(STORE.read_text())
        return [Task(**t) for t in data]
    except (json.JSONDecodeError, TypeError) as e:
        sys.exit(f"error: corrupt store at {STORE}: {e}")


def save(tasks: list[Task]) -> None:
    STORE.write_text(json.dumps([asdict(t) for t in tasks], indent=2))


def short_id(task_id: str) -> str:
    return task_id[:8]


def find(tasks: list[Task], prefix: str) -> Optional[Task]:
    matches = [t for t in tasks if t.id.startswith(prefix)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        print(f"error: ambiguous ID '{prefix}' — matches {len(matches)} tasks", file=sys.stderr)
    else:
        print(f"error: task '{prefix}' not found", file=sys.stderr)
    return None


def matches_filter(
    task: Task,
    status: Optional[str],
    tag: Optional[str],
    search: Optional[str],
) -> bool:
    """
    AND-composition of all active filter conditions.
    Tag: exact match, case-insensitive.
    Search: case-insensitive substring on title.
    """
    if status is not None and task.status != status:
        return False
    if tag is not None and tag.lower() not in (t.lower() for t in task.tags):
        return False
    if search is not None and search.lower() not in task.title.lower():
        return False
    return True


def cmd_add(args) -> None:
    tasks = load()
    task = Task(
        id=str(uuid.uuid4()),
        title=args.title,
        tags=[t.lstrip("#") for t in args.tag] if args.tag else [],
    )
    tasks.append(task)
    save(tasks)
    print(f"+ [{short_id(task.id)}] {task.title}")


def cmd_done(args) -> None:
    tasks = load()
    task = find(tasks, args.id)
    if not task:
        sys.exit(1)
    if task.status == "done":
        print(f"already done: [{short_id(task.id)}] {task.title}")
        return
    task.status = "done"
    task.completed_at = _now()
    save(tasks)
    print(f"✓ [{short_id(task.id)}] {task.title}")


def cmd_rm(args) -> None:
    tasks = load()
    task = find(tasks, args.id)
    if not task:
        sys.exit(1)
    tasks = [t for t in tasks if t.id != task.id]
    save(tasks)
    print(f"- [{short_id(task.id)}] {task.title}")


def cmd_ls(args) -> None:
    tasks = load()
    status_filter = None if args.status == "all" else args.status
    filtered = [t for t in tasks if matches_filter(t, status_filter, args.tag, args.search)]
    if not filtered:
        print("no tasks.")
        return
    for t in sorted(filtered, key=lambda t: t.created_at):
        mark = "✓" if t.status == "done" else "○"
        tag_str = "  " + "  ".join(f"#{tag}" for tag in t.tags) if t.tags else ""
        ts = t.completed_at if t.status == "done" else t.created_at
        print(f"{mark} [{short_id(t.id)}] {t.title}{tag_str}  ({ts})")


def main() -> None:
    parser = ArgumentParser(prog="tasks", description=__doc__,
                            formatter_class=RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", metavar="COMMAND")
    sub.required = True

    p = sub.add_parser("add", help="add a task")
    p.add_argument("title")
    p.add_argument("--tag", action="append", metavar="TAG")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("done", help="mark a task complete")
    p.add_argument("id")
    p.set_defaults(func=cmd_done)

    p = sub.add_parser("rm", help="remove a task")
    p.add_argument("id")
    p.set_defaults(func=cmd_rm)

    p = sub.add_parser("ls", help="list tasks")
    p.add_argument("--status", choices=["pending", "done", "all"], default="pending")
    p.add_argument("--tag", metavar="TAG")
    p.add_argument("--search", metavar="QUERY")
    p.set_defaults(func=cmd_ls)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

# In cmd_ls, split on comma before passing:
tag_filter = args.tag.split(",") if args.tag else None  # list[str] | None

def matches_filter(task, status, tags: list[str] | None, search) -> bool:
    # tags=None → skip; tags=['etl','urgent'] → ANY match (OR)
    if tags is not None and not any(tg.lower() in (t.lower() for t in task.tags) for tg in tags):
        return False
    ...