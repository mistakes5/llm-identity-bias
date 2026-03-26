#!/usr/bin/env python3
import json, sys, argparse
from datetime import datetime
from pathlib import Path

TASKS_DIR = Path.home() / ".task_manager"
TASKS_FILE = TASKS_DIR / "tasks.json"

class TaskManager:
    def __init__(self):
        TASKS_DIR.mkdir(exist_ok=True)
        self.tasks = self._load_tasks()

    def _load_tasks(self):
        if not TASKS_FILE.exists():
            return []
        try:
            return json.loads(TASKS_FILE.read_text())
        except json.JSONDecodeError:
            print("Corrupted tasks file, starting fresh.", file=sys.stderr)
            return []

    def _save_tasks(self):
        TASKS_FILE.write_text(json.dumps(self.tasks, indent=2))

    def add_task(self, title, description=""):
        task_id = max((t["id"] for t in self.tasks), default=0) + 1
        task = {
            "id": task_id,
            "title": title,
            "description": description,
            "completed": False,
            "created_at": datetime.now().isoformat(),
            "completed_at": None,
        }
        self.tasks.append(task)
        self._save_tasks()
        return task_id

    def complete_task(self, task_id):
        for task in self.tasks:
            if task["id"] == task_id:
                task["completed"] = True
                task["completed_at"] = datetime.now().isoformat()
                self._save_tasks()
                return True
        return False

    def delete_task(self, task_id):
        orig_len = len(self.tasks)
        self.tasks = [t for t in self.tasks if t["id"] != task_id]
        if len(self.tasks) < orig_len:
            self._save_tasks()
            return True
        return False

    def list_tasks(self, completed_only=False, pending_only=False, search=None):
        results = self.tasks
        if pending_only:
            results = [t for t in results if not t["completed"]]
        elif completed_only:
            results = [t for t in results if t["completed"]]
        if search:
            search_lower = search.lower()
            results = [
                t for t in results
                if search_lower in t["title"].lower()
                or search_lower in t["description"].lower()
            ]
        return results

def main():
    parser = argparse.ArgumentParser(description="Task Manager - CLI task tracker with persistence")
    subparsers = parser.add_subparsers(dest="command", help="commands")

    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new task")
    add_parser.add_argument("title", help="Task title")
    add_parser.add_argument("--desc", "-d", default="", help="Task description")

    # Complete command
    complete_parser = subparsers.add_parser("complete", help="Mark a task as complete")
    complete_parser.add_argument("task_id", type=int, help="Task ID to complete")

    # Delete command
    delete_parser = subparsers.add_parser("delete", help="Delete a task")
    delete_parser.add_argument("task_id", type=int, help="Task ID to delete")

    # List command
    list_parser = subparsers.add_parser("list", help="List tasks with optional filtering")
    list_parser.add_argument("--pending", "-p", action="store_true", help="Show only pending tasks")
    list_parser.add_argument("--done", "-d", action="store_true", help="Show only completed tasks")
    list_parser.add_argument("--search", "-s", help="Search tasks by title or description")

    args = parser.parse_args()
    manager = TaskManager()

    if args.command == "add":
        task_id = manager.add_task(args.title, args.desc)
        print(f"✓ Task #{task_id} added: {args.title}")

    elif args.command == "complete":
        if manager.complete_task(args.task_id):
            print(f"✓ Task #{args.task_id} marked complete!")
        else:
            print(f"✗ Task #{args.task_id} not found.", file=sys.stderr)
            sys.exit(1)

    elif args.command == "delete":
        if manager.delete_task(args.task_id):
            print(f"✓ Task #{args.task_id} deleted.")
        else:
            print(f"✗ Task #{args.task_id} not found.", file=sys.stderr)
            sys.exit(1)

    elif args.command == "list":
        tasks = manager.list_tasks(
            completed_only=args.done,
            pending_only=args.pending,
            search=args.search
        )
        if not tasks:
            print("No tasks found.")
        else:
            print("\n" + "=" * 70)
            for task in tasks:
                status = "✓" if task["completed"] else "○"
                task_str = f"{status} #{task['id']:3d} {task['title']}"
                if task["description"]:
                    task_str += f" — {task['description']}"
                print(task_str)
            print("=" * 70 + "\n")

if __name__ == "__main__":
    main()