import json
import os
import argparse
from datetime import datetime
from pathlib import Path

TASKS_FILE = Path.home() / ".tasks.json"


def load_tasks() -> list[dict]:
    if TASKS_FILE.exists():
        with open(TASKS_FILE) as f:
            return json.load(f)
    return []


def save_tasks(tasks: list[dict]) -> None:
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, indent=2)


def add_task(title: str, priority: str = "medium", tags: list[str] = None) -> dict:
    tasks = load_tasks()
    task = {
        "id": max((t["id"] for t in tasks), default=0) + 1,
        "title": title,
        "done": False,
        "priority": priority,
        "tags": tags or [],
        "created_at": datetime.now().isoformat(),
        "completed_at": None,
    }
    tasks.append(task)
    save_tasks(tasks)
    print(f"✅ Added task #{task['id']}: {title}")
    return task


def complete_task(task_id: int) -> None:
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task["done"] = True
            task["completed_at"] = datetime.now().isoformat()
            save_tasks(tasks)
            print(f"🎉 Completed task #{task_id}: {task['title']}")
            return
    print(f"❌ Task #{task_id} not found.")


def delete_task(task_id: int) -> None:
    tasks = load_tasks()
    updated = [t for t in tasks if t["id"] != task_id]
    if len(updated) == len(tasks):
        print(f"❌ Task #{task_id} not found.")
        return
    save_tasks(updated)
    print(f"🗑️  Deleted task #{task_id}.")


def list_tasks(
    show_done: bool = False,
    priority: str = None,
    tag: str = None,
) -> None:
    tasks = load_tasks()

    # Apply filters
    filtered = [t for t in tasks if show_done or not t["done"]]
    if priority:
        filtered = [t for t in filtered if t["priority"] == priority]
    if tag:
        filtered = [t for t in filtered if tag in t["tags"]]

    if not filtered:
        print("No tasks found.")
        return

    priority_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    status_icon = {True: "✔", False: "○"}

    print(f"\n{'ID':<5} {'St':<3} {'Pri':<3} {'Title':<40} {'Tags'}")
    print("─" * 70)
    for t in filtered:
        icon = priority_icon.get(t["priority"], "⚪")
        done = status_icon[t["done"]]
        tags = ", ".join(t["tags"]) if t["tags"] else ""
        title = t["title"][:38] + ".." if len(t["title"]) > 40 else t["title"]
        print(f"#{t['id']:<4} {done:<3} {icon:<3} {title:<40} {tags}")
    print(f"\n{len(filtered)} task(s) shown.")


def main():
    parser = argparse.ArgumentParser(
        description="📋 CLI Task Manager",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = subparsers.add_parser("add", help="Add a new task")
    p_add.add_argument("title", help="Task title")
    p_add.add_argument(
        "-p", "--priority",
        choices=["low", "medium", "high"],
        default="medium",
        help="Task priority (default: medium)",
    )
    p_add.add_argument(
        "-t", "--tags",
        nargs="*",
        default=[],
        help="Optional tags, e.g. -t work personal",
    )

    # done
    p_done = subparsers.add_parser("done", help="Mark a task as complete")
    p_done.add_argument("id", type=int, help="Task ID")

    # delete
    p_del = subparsers.add_parser("delete", help="Delete a task")
    p_del.add_argument("id", type=int, help="Task ID")

    # list
    p_list = subparsers.add_parser("list", help="List tasks")
    p_list.add_argument(
        "-a", "--all",
        action="store_true",
        help="Include completed tasks",
    )
    p_list.add_argument(
        "-p", "--priority",
        choices=["low", "medium", "high"],
        help="Filter by priority",
    )
    p_list.add_argument(
        "-t", "--tag",
        help="Filter by tag",
    )

    args = parser.parse_args()

    match args.command:
        case "add":
            add_task(args.title, priority=args.priority, tags=args.tags)
        case "done":
            complete_task(args.id)
        case "delete":
            delete_task(args.id)
        case "list":
            list_tasks(
                show_done=args.all,
                priority=args.priority,
                tag=args.tag,
            )


if __name__ == "__main__":
    main()