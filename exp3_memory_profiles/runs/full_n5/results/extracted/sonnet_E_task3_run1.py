# tasks.py - A simple command-line task manager
# Run it like this:
#   python tasks.py add "Buy groceries"
#   python tasks.py list
#   python tasks.py done 1
#   python tasks.py filter pending

import json        # for reading/writing the tasks file (built into Python)
import sys         # for reading the words you type in the terminal
import os          # for checking if the save file exists
from datetime import date  # for recording today's date when a task is created

# The file where all tasks are saved between sessions
TASKS_FILE = "tasks.json"


# ─── LOADING AND SAVING ───────────────────────────────────────────────────────

def load_tasks():
    """Read all tasks from the JSON file. Returns an empty list on first run."""
    if not os.path.exists(TASKS_FILE):
        return []   # no save file yet — start fresh

    with open(TASKS_FILE, "r") as f:
        return json.load(f)   # parses the file into a Python list of dicts


def save_tasks(tasks):
    """Write the current task list back to the JSON file."""
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, indent=2)   # indent=2 keeps the file human-readable


# ─── CORE TASK OPERATIONS ─────────────────────────────────────────────────────

def add_task(tasks, title):
    """Create a new task dict and append it to the list."""
    # Pick the next available ID (max existing + 1, or 1 if list is empty)
    next_id = max(task["id"] for task in tasks) + 1 if tasks else 1

    new_task = {
        "id":      next_id,
        "title":   title,
        "done":    False,               # every new task starts as not done
        "created": str(date.today()),   # e.g. "2026-03-24"
    }

    tasks.append(new_task)
    print(f"✓ Added task #{next_id}: {title}")


def complete_task(tasks, task_id):
    """Find a task by ID and flip its 'done' flag to True."""
    for task in tasks:
        if task["id"] == task_id:
            task["done"] = True
            print(f"✓ Completed task #{task_id}: {task['title']}")
            return   # stop looping once we've found the task

    print(f"✗ No task found with ID #{task_id}")


def list_tasks(tasks):
    """Print all tasks in a neat table."""
    if not tasks:
        print('No tasks yet! Try: python tasks.py add "your task here"')
        return

    # :<N pads text to N characters wide so columns line up
    print(f"\n  {'ID':<5} {'Status':<12} {'Created':<13} Title")
    print("  " + "─" * 55)

    for task in tasks:
        status = "✓ done" if task["done"] else "○ pending"
        print(f"  {task['id']:<5} {status:<12} {task['created']:<13} {task['title']}")

    print()


# ─── YOUR TURN: filter_tasks ──────────────────────────────────────────────────

def filter_tasks(tasks, filter_by):
    """
    Return a filtered list of tasks based on filter_by.

    Parameters:
        tasks     -- the full list of task dictionaries
        filter_by -- "done", "pending", or a search keyword

    Each task is a dict:
        { "id": 1, "title": "Buy groceries", "done": False, "created": "2026-03-24" }

    Rules to implement:
        "done"    → keep tasks where task["done"] is True
        "pending" → keep tasks where task["done"] is False
        anything else → keep tasks where filter_by appears in task["title"]
                        (use .lower() on both sides so "BUY" matches "buy")

    Build your result like this:
        matching = []
        for task in tasks:
            if <your condition>:
                matching.append(task)
        return matching
    """

    # TODO: Replace `pass` with your implementation!
    pass


# ─── COMMAND-LINE INTERFACE ───────────────────────────────────────────────────

def main():
    """Parse sys.argv and call the right function."""

    # sys.argv example for "python tasks.py add Buy milk":
    #   sys.argv[0] = "tasks.py"
    #   sys.argv[1] = "add"
    #   sys.argv[2] = "Buy"
    #   sys.argv[3] = "milk"

    if len(sys.argv) < 2:
        print("\nUsage:")
        print('  python tasks.py add "task title"    add a new task')
        print("  python tasks.py list                show all tasks")
        print("  python tasks.py done <id>           mark a task complete")
        print("  python tasks.py filter done         show completed tasks")
        print("  python tasks.py filter pending      show pending tasks")
        print("  python tasks.py filter <word>       search by keyword\n")
        return

    tasks = load_tasks()       # load saved tasks before doing anything
    command = sys.argv[1].lower()

    if command == "add":
        if len(sys.argv) < 3:
            print('Provide a title — e.g.: python tasks.py add "Buy milk"')
        else:
            title = " ".join(sys.argv[2:])   # join extra words into one string
            add_task(tasks, title)
            save_tasks(tasks)

    elif command == "done":
        if len(sys.argv) < 3:
            print("Provide an ID — e.g.: python tasks.py done 1")
        else:
            complete_task(tasks, int(sys.argv[2]))   # int() converts "2" → 2
            save_tasks(tasks)

    elif command == "list":
        list_tasks(tasks)

    elif command == "filter":
        if len(sys.argv) < 3:
            print("Provide a filter: done, pending, or a search keyword")
        else:
            results = filter_tasks(tasks, sys.argv[2].lower())

            if results is None:
                print("\n⚠  filter_tasks() returned None.")
                print("   Open tasks.py, find the TODO, and write your code!\n")
            elif not results:
                print(f'No tasks matched "{sys.argv[2]}".')
            else:
                print(f'Results for "{sys.argv[2]}":')
                list_tasks(results)

    else:
        print(f'Unknown command: "{command}"')
        print("Valid commands: add, list, done, filter")


if __name__ == "__main__":
    main()

def filter_tasks(tasks, filter_by):
    matching = []                   # start with an empty results list

    for task in tasks:
        if filter_by == "done":
            # TODO: add the task if it IS done
            pass
        elif filter_by == "pending":
            # TODO: add the task if it is NOT done
            pass
        else:
            # TODO: add the task if filter_by appears in the title
            # Hint: use  filter_by in task["title"].lower()
            pass

    return matching