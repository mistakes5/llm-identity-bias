#!/usr/bin/env python3
"""
Command-line task manager with persistence via JSON.
Usage: python tasks.py <command> [options]
"""

import json
import argparse
from pathlib import Path
from datetime import datetime

TASKS_FILE = Path.home() / ".tasks.json"


# ── Persistence ────────────────────────────────────────────────────────────────

def load_tasks() -> list[dict]:
    if TASKS_FILE.exists():
        return json.loads(TASKS_FILE.read_text())
    return []


def save_tasks(tasks: list[dict]) -> None:
    TASKS_FILE.write_text(json.dumps(tasks, indent=2))


def next_id(tasks: list[dict]) -> int:
    return max((t["id"] for t in tasks), default=0) + 1


# ── Commands ───────────────────────────────────────────────────────────────────

def cmd_add(args) -> None:
    tasks = load_tasks()
    task = {
        "id": next_id(tasks),
        "title": " ".join(args.title),
        "tag": args.tag,
        "done": False,
        "created": datetime.now().isoformat(timespec="seconds"),
        "completed": None,
    }
    tasks.append(task)
    save_tasks(tasks)
    print(f"✓ Added [{task['id']}] {task['title']}" +
          (f"  #{task['tag']}" if task["tag"] else ""))


def cmd_done(args) -> None:
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == args.id:
            if task["done"]:
                print(f"Task {args.id} is already complete.")
                return
            task["done"] = True
            task["completed"] = datetime.now().isoformat(timespec="seconds")
            save_tasks(tasks)
            print(f"✓ Completed [{task['id']}] {task['title']}")
            return
    print(f"No task with id {args.id}.")


def cmd_delete(args) -> None:
    tasks = load_tasks()
    remaining = [t for t in tasks if t["id"] != args.id]
    if len(remaining) == len(tasks):
        print(f"No task with id {args.id}.")
        return
    save_tasks(remaining)
    print(f"Deleted task {args.id}.")


def cmd_list(args) -> None:
    tasks = load_tasks()

    # Apply filters
    if args.tag:
        tasks = [t for t in tasks if t.get("tag") == args.tag]
    if args.status == "done":
        tasks = [t for t in tasks if t["done"]]
    elif args.status == "pending":
        tasks = [t for t in tasks if not t["done"]]

    if not tasks:
        print("No tasks found.")
        return

    # Display
    col_w = max(len(t["title"]) for t in tasks) + 2
    print(f"\n{'ID':<5} {'STATUS':<10} {'TITLE':<{col_w}} {'TAG':<12} CREATED")
    print("─" * (5 + 10 + col_w + 12 + 20))
    for t in tasks:
        status = "✓ done" if t["done"] else "○ pending"
        tag = f"#{t['tag']}" if t.get("tag") else ""
        created = t["created"][:10]
        print(f"{t['id']:<5} {status:<10} {t['title']:<{col_w}} {tag:<12} {created}")
    print()


def cmd_tags(args) -> None:
    tasks = load_tasks()
    tags = sorted({t["tag"] for t in tasks if t.get("tag")})
    if not tags:
        print("No tags found.")
    else:
        print("Tags: " + "  ".join(f"#{t}" for t in tags))


# ── CLI Setup ──────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tasks",
        description="Simple persistent task manager"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = sub.add_parser("add", help="Add a new task")
    p_add.add_argument("title", nargs="+", help="Task title (no quotes needed)")
    p_add.add_argument("--tag", "-t", help="Optional tag for grouping")
    p_add.set_defaults(func=cmd_add)

    # done
    p_done = sub.add_parser("done", help="Mark a task complete")
    p_done.add_argument("id", type=int, help="Task ID")
    p_done.set_defaults(func=cmd_done)

    # delete
    p_del = sub.add_parser("delete", help="Delete a task")
    p_del.add_argument("id", type=int, help="Task ID")
    p_del.set_defaults(func=cmd_delete)

    # list
    p_list = sub.add_parser("list", help="List tasks")
    p_list.add_argument("--tag", "-t", help="Filter by tag")
    p_list.add_argument(
        "--status", "-s",
        choices=["all", "done", "pending"],
        default="all",
        help="Filter by status (default: all)"
    )
    p_list.set_defaults(func=cmd_list)

    # tags
    p_tags = sub.add_parser("tags", help="Show all tags in use")
    p_tags.set_defaults(func=cmd_tags)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()