# todo.py — A simple command-line task manager
#
# How to use:
#   python todo.py add "Buy groceries"
#   python todo.py list
#   python todo.py list --filter pending
#   python todo.py done 1
#
# Tasks are saved in tasks.json so they survive between sessions.

import json        # lets us save/load Python data as a text file
import os          # lets us check if a file exists
import argparse    # helps us build command-line commands with --flags
from datetime import datetime  # lets us record when a task was added

# ─── SETTINGS ────────────────────────────────────────────────────────────────

# The file where tasks will be stored.
# It gets created automatically the first time you add a task.
TASKS_FILE = "tasks.json"


# ─── FILE HELPERS ─────────────────────────────────────────────────────────────

def load_tasks():
    """Read tasks from the JSON file. Returns [] if the file doesn't exist yet."""
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, "r") as f:
            # json.load() converts the saved text back into a Python list
            return json.load(f)
    return []   # first run — no file yet, so start fresh


def save_tasks(tasks):
    """Write the tasks list back to the JSON file after every change."""
    with open(TASKS_FILE, "w") as f:
        # indent=2 keeps the file human-readable (nice indentation)
        json.dump(tasks, f, indent=2)


# ─── TASK ACTIONS ─────────────────────────────────────────────────────────────

def add_task(description):
    """Create a new task dictionary and append it to the saved list."""
    tasks = load_tasks()

    # Each task is a plain dictionary — no classes needed!
    new_task = {
        "id": len(tasks) + 1,          # next available number: 1, 2, 3…
        "description": description,
        "done": False,                  # all new tasks start as pending
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }

    tasks.append(new_task)
    save_tasks(tasks)
    print(f"  Added task #{new_task['id']}: {description}")


def complete_task(task_id):
    """Find a task by ID and flip its 'done' flag to True."""
    tasks = load_tasks()

    for task in tasks:
        if task["id"] == task_id:
            task["done"] = True
            save_tasks(tasks)
            print(f"  Completed task #{task_id}: {task['description']}")
            return  # stop looping — we found what we needed

    print(f"  Task #{task_id} not found. Run 'python todo.py list' to see valid IDs.")


def filter_tasks(tasks, filter_by):
    """
    Return a filtered copy of the tasks list.

    filter_by can be:
      "all"     → every task
      "pending" → only tasks where done == False
      "done"    → only tasks where done == True

    ── YOUR TURN ───────────────────────────────────────────────────────────
    Implement this function! It should be about 6–8 lines.

    Hint: A list comprehension looks like:
        result = [item for item in my_list if some_condition]

    For example, to keep only tasks that are NOT done yet:
        return [task for task in tasks if not task["done"]]

    Think about:
      • What should "all" return? (simplest case — no filtering needed)
      • How do you check if a task is done? (look at the "done" key)
      • What if an unknown filter value is passed? Print a warning and
        fall back to returning everything.
    ─────────────────────────────────────────────────────────────────────────
    """
    # ↓ Replace this 'pass' with your code ↓
    pass


def list_tasks(filter_by="all"):
    """Print tasks in a readable table, using filter_tasks() to narrow results."""
    tasks = load_tasks()
    filtered = filter_tasks(tasks, filter_by)

    if not filtered:
        if filter_by == "all":
            print('  No tasks yet. Add one: python todo.py add "Task name"')
        else:
            print(f"  No '{filter_by}' tasks found.")
        return

    label = f"Tasks ({filter_by})" if filter_by != "all" else "All Tasks"
    print(f"\n  {label}")
    print(f"  {'─' * 58}")
    print(f"  {'#':<5}  {'Status':<10}  {'Added':<17}  Description")
    print(f"  {'─' * 58}")

    for task in filtered:
        status = "✓ done   " if task["done"] else "○ pending"
        print(f"  {task['id']:<5}  {status:<10}  {task['created_at']:<17}  {task['description']}")

    print(f"  {'─' * 58}")
    print(f"  {len(filtered)} task(s)\n")


# ─── COMMAND-LINE INTERFACE ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="A simple command-line task manager.",
        epilog='Example: python todo.py add "Finish homework"'
    )
    subparsers = parser.add_subparsers(dest="command", metavar="command")

    # python todo.py add "Some description"
    add_parser = subparsers.add_parser("add", help="Add a new task")
    add_parser.add_argument("description", help="What the task is about")

    # python todo.py done 3
    done_parser = subparsers.add_parser("done", help="Mark a task as completed")
    done_parser.add_argument("id", type=int, help="Task ID to complete")

    # python todo.py list --filter pending
    list_parser = subparsers.add_parser("list", help="Show tasks")
    list_parser.add_argument(
        "--filter",
        choices=["all", "pending", "done"],
        default="all",
        help="Filter by status (default: all)"
    )

    args = parser.parse_args()

    if args.command == "add":
        add_task(args.description)
    elif args.command == "done":
        complete_task(args.id)
    elif args.command == "list":
        list_tasks(args.filter)
    else:
        parser.print_help()


# This block only runs when you execute the file directly
if __name__ == "__main__":
    main()

def filter_tasks(tasks, filter_by):
    if filter_by == "all":
        # TODO: what should we return here? (hint: return everything)
        ...
    elif filter_by == "pending":
        # TODO: return only tasks that are NOT done yet
        ...
    elif filter_by == "done":
        # TODO: return only tasks that ARE done
        ...
    else:
        # Unknown filter — warn the user and fall back to everything
        print(f"  Unknown filter '{filter_by}'. Showing all tasks.")
        ...

return [task for task in tasks if not task["done"]]
#       ↑ build a new list    ↑ loop through each   ↑ only keep if not done