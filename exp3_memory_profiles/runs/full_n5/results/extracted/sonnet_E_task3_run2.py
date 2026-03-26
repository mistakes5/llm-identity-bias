# tasks.py — A command-line task manager
#
# How to run it:
#   python tasks.py add "Buy groceries"
#   python tasks.py add "Study Python" high
#   python tasks.py done 1
#   python tasks.py list
#   python tasks.py filter done

import json        # lets us save Python dicts/lists to a text file
import sys         # gives us sys.argv — the words typed on the command line
import os          # lets us check if a file exists with os.path.exists()
from datetime import date  # lets us record today's date when a task is created

TASKS_FILE = "tasks.json"   # tasks are saved here between sessions


# ─── Loading & Saving ────────────────────────────────────────────────────────

def load_tasks():
    """Read the tasks list from disk. Returns [] if nothing saved yet."""
    if not os.path.exists(TASKS_FILE):
        return []   # first run — no file yet

    with open(TASKS_FILE, "r") as f:
        return json.load(f)   # json.load() converts text → Python list of dicts

def save_tasks(tasks):
    """Write the tasks list to disk so it persists after the program exits."""
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, indent=2)   # indent=2 makes the file human-readable


# ─── Adding ──────────────────────────────────────────────────────────────────

def add_task(title, priority="normal"):
    tasks = load_tasks()

    # max() finds the biggest "id" in the list; default=0 handles an empty list
    next_id = max((t["id"] for t in tasks), default=0) + 1

    new_task = {
        "id":       next_id,
        "title":    title,
        "done":     False,              # all tasks start as not done
        "priority": priority,           # "low", "normal", or "high"
        "created":  str(date.today()),  # e.g. "2026-03-24"
    }

    tasks.append(new_task)
    save_tasks(tasks)
    print(f"✅  Added #{next_id}: \"{title}\"  [{priority} priority]")


# ─── Completing ──────────────────────────────────────────────────────────────

def complete_task(task_id):
    tasks = load_tasks()

    for task in tasks:
        if task["id"] == task_id:
            task["done"] = True
            save_tasks(tasks)
            print(f"✔️   Completed #{task_id}: \"{task['title']}\"")
            return   # found it — stop looping

    print(f"❌  No task found with ID #{task_id}.")


# ─── Listing ─────────────────────────────────────────────────────────────────

def list_tasks(tasks=None):
    """Print tasks in a table. Pass a list to show a filtered subset."""
    if tasks is None:
        tasks = load_tasks()

    if not tasks:
        print("\n  No tasks yet!  Try:  python tasks.py add \"Your first task\"\n")
        return

    print(f"\n  {'ID':<4}  {'STATUS':<9}  {'PRIORITY':<8}  TITLE")
    print("  " + "─" * 50)

    for task in tasks:
        status = "✔ done " if task["done"] else "○ todo "
        # :<4 = left-aligned, padded to 4 characters wide
        print(f"  {task['id']:<4}  {status:<9}  {task['priority']:<8}  {task['title']}")
    print()


# ─── Filtering  ← YOUR TURN! ─────────────────────────────────────────────────

def filter_tasks(filter_by):
    """
    Show only tasks matching the given filter word.

    filter_by can be:
        "done"   → only finished tasks
        "todo"   → only unfinished tasks
        "high"   → only high-priority tasks
        "normal" → only normal-priority tasks
        "low"    → only low-priority tasks

    Hints:
        - task["done"] is True or False
        - task["priority"] is "high", "normal", or "low"
        - A list comprehension looks like:  [t for t in tasks if <condition>]
    """
    tasks = load_tasks()

    # ── TODO: build the filtered list here ────────────────────────────────────
    # filtered = ???
    #
    # ── Then display it ───────────────────────────────────────────────────────
    # list_tasks(filtered)
    #
    # ── If the filter isn't recognised, tell the user ─────────────────────────
    # print(f"Unknown filter '{filter_by}'. Try: done, todo, high, normal, low")
    # ──────────────────────────────────────────────────────────────────────────
    print("(filter_tasks not implemented yet — this is your part!)")


# ─── Help & Entry Point ──────────────────────────────────────────────────────

def show_help():
    print("""
  Task Manager — Commands:
    python tasks.py add "Title"           Add a task (normal priority)
    python tasks.py add "Title" high      Add a high-priority task
    python tasks.py done <id>             Mark a task as complete
    python tasks.py list                  Show all tasks
    python tasks.py filter <word>         Show filtered tasks

  Filter words: done  todo  high  normal  low
    """)

# sys.argv = ["tasks.py", "add", "Buy milk", "high"]
#              [0]          [1]    [2]          [3]
if len(sys.argv) < 2:
    show_help()
else:
    command = sys.argv[1]

    if command == "add":
        if len(sys.argv) < 3:
            print("Usage: python tasks.py add \"Task title\" [low|normal|high]")
        else:
            title    = sys.argv[2]
            priority = sys.argv[3] if len(sys.argv) > 3 else "normal"
            add_task(title, priority)

    elif command == "done":
        if len(sys.argv) < 3:
            print("Usage: python tasks.py done <id>")
        else:
            task_id = int(sys.argv[2])   # int() converts "3" → 3
            complete_task(task_id)

    elif command == "list":
        list_tasks()

    elif command == "filter":
        if len(sys.argv) < 3:
            print("Usage: python tasks.py filter <done|todo|high|normal|low>")
        else:
            filter_tasks(sys.argv[2])

    else:
        print(f"Unknown command: '{command}'")
        show_help()

tasks = load_tasks()

# filtered = ???        ← your code goes here

# list_tasks(filtered)  ← then show the results

filtered = [t for t in tasks if t["done"] == True]