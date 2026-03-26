import json       # lets us save Python data to a file and load it back
import os         # lets us check if a file already exists
from datetime import date  # gives us today's date

# The file where tasks are stored between sessions (same folder as this script)
TASKS_FILE = "tasks.json"


# ── Loading & Saving ───────────────────────────────────────────────────────────

def load_tasks():
    """Read tasks from disk. Return empty list if file doesn't exist yet."""
    if not os.path.exists(TASKS_FILE):
        return []  # First run — no file yet, that's fine
    with open(TASKS_FILE, "r") as f:
        return json.load(f)  # Converts saved text back into a Python list


def save_tasks(tasks):
    """Write the task list to disk so nothing is lost between runs."""
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, indent=2)  # indent=2 makes it human-readable


# ── Task Operations ────────────────────────────────────────────────────────────

def add_task(tasks, title):
    """Create a new task dictionary and append it to the list."""
    # Assign an ID: 1 if first task, otherwise highest existing ID + 1
    if len(tasks) == 0:
        new_id = 1
    else:
        new_id = max(task["id"] for task in tasks) + 1

    new_task = {
        "id":      new_id,
        "title":   title,
        "done":    False,              # all new tasks start as not done
        "created": str(date.today())   # records "2024-03-15" style string
    }
    tasks.append(new_task)
    save_tasks(tasks)
    print(f"\n  ✓ Task #{new_id} added: \"{title}\"")


def complete_task(tasks, task_id):
    """Find the task with the given ID and mark it done."""
    for task in tasks:
        if task["id"] == task_id:
            if task["done"]:
                print(f"\n  Task #{task_id} is already completed.")
                return
            task["done"] = True
            save_tasks(tasks)
            print(f"\n  ✓ Marked done: \"{task['title']}\"")
            return
    print(f"\n  No task found with ID #{task_id}.")


def delete_task(tasks, task_id):
    """Remove a task from the list using a list comprehension."""
    original_count = len(tasks)
    # Keep every task whose ID does NOT match (skips the one we want to delete)
    tasks[:] = [task for task in tasks if task["id"] != task_id]
    if len(tasks) < original_count:
        save_tasks(tasks)
        print(f"\n  ✓ Task #{task_id} deleted.")
    else:
        print(f"\n  No task found with ID #{task_id}.")


def list_tasks(tasks):
    """Print all tasks in a readable table."""
    if len(tasks) == 0:
        print("\n  No tasks yet! Add one with option 1.")
        return

    print("\n  ┌─────────────────────────────────────────────────────┐")
    print("  │  ID   Status     Title                    Added     │")
    print("  ├─────────────────────────────────────────────────────┤")
    for task in tasks:
        status = "✅ done   " if task["done"] else "⬜ pending"
        # :<24 pads the title to 24 characters so columns line up neatly
        print(f"  │  #{task['id']:<3}  {status}  {task['title']:<24}  {task['created']}  │")

    done_count    = sum(1 for task in tasks if task["done"])
    pending_count = len(tasks) - done_count
    print("  └─────────────────────────────────────────────────────┘")
    print(f"     {done_count} done · {pending_count} pending · {len(tasks)} total\n")


def filter_tasks(tasks, filter_type):
    """
    Return a filtered subset of tasks.

    Parameters:
        tasks       — the full list of task dictionaries
        filter_type — the string the user typed (e.g. "done", "pending", or any word)

    Returns a list of matching task dictionaries (or [] if nothing matches).

    ────────────────────────────────────────────────────────────────
    TODO: Implement this function!  It's your turn. ✏️

    Handle three cases:

      1.  filter_type == "done"
              → return only tasks where task["done"] is True

      2.  filter_type == "pending"
              → return only tasks where task["done"] is False

      3.  anything else
              → treat it as a keyword search
              → return tasks whose title contains that word
              → Hint: `filter_type in task["title"].lower()`
                makes it case-insensitive (so "buy" matches "Buy Milk")

    Approach — use if/elif/else with list comprehensions:
        return [task for task in tasks if <your condition>]
    ────────────────────────────────────────────────────────────────
    """
    return None  # ← replace this with your code


# ── Menu & Main Loop ──────────────────────────────────────────────────────────

def show_menu():
    print("\n  ╔══════════════════════════════╗")
    print("  ║      📝  Task Manager        ║")
    print("  ╠══════════════════════════════╣")
    print("  ║  1. Add a task               ║")
    print("  ║  2. Complete a task          ║")
    print("  ║  3. List all tasks           ║")
    print("  ║  4. Filter / search tasks    ║")
    print("  ║  5. Delete a task            ║")
    print("  ║  6. Quit                     ║")
    print("  ╚══════════════════════════════╝")


def main():
    """Load tasks, then show the menu in a loop until the user quits."""
    tasks = load_tasks()
    print("\n  Welcome back! Tasks loaded." if tasks else "\n  Welcome! No tasks yet.")

    while True:  # keep looping until the user hits 'break' via option 6
        show_menu()
        choice = input("  Choose (1–6): ").strip()

        if choice == "1":
            title = input("  Task title: ").strip()
            if title:
                add_task(tasks, title)
            else:
                print("\n  Title can't be empty.")

        elif choice == "2":
            list_tasks(tasks)
            try:
                task_id = int(input("  Task ID to complete: ").strip())
                complete_task(tasks, task_id)
            except ValueError:
                print("\n  Please enter a number.")

        elif choice == "3":
            list_tasks(tasks)

        elif choice == "4":
            print("\n  done / pending / <search word>")
            filter_type = input("  Filter by: ").strip().lower()
            results = filter_tasks(tasks, filter_type)

            if results is None:
                print("\n  ⚠  filter_tasks() not implemented yet — that's your next step!")
            elif len(results) == 0:
                print(f"\n  No tasks match \"{filter_type}\".")
            else:
                list_tasks(results)

        elif choice == "5":
            list_tasks(tasks)
            try:
                task_id = int(input("  Task ID to delete: ").strip())
                confirm = input(f"  Delete #{task_id}? Type 'yes': ").strip().lower()
                if confirm == "yes":
                    delete_task(tasks, task_id)
                else:
                    print("\n  Cancelled.")
            except ValueError:
                print("\n  Please enter a number.")

        elif choice == "6":
            print("\n  Goodbye! Tasks saved. 👋\n")
            break

        else:
            print("\n  Please enter 1–6.")


if __name__ == "__main__":
    main()

def filter_tasks(tasks, filter_type):
    if filter_type == "done":
        return [task for task in tasks if ___________]

    elif filter_type == "pending":
        return [task for task in tasks if ___________]

    else:
        return [task for task in tasks if filter_type in task["title"]._______()]