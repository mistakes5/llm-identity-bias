import json
import os
from datetime import datetime

# This is the file where we will save all tasks between sessions
TASKS_FILE = "tasks.json"


# ============================================================================
# HELPER FUNCTIONS - These do the actual work
# ============================================================================

def load_tasks():
    """
    Load all tasks from the JSON file.
    If the file doesn't exist yet, return an empty list.
    """
    if not os.path.exists(TASKS_FILE):
        return []

    try:
        with open(TASKS_FILE, "r") as file:
            tasks = json.load(file)
        return tasks
    except json.JSONDecodeError:
        # If the file is corrupted, start fresh
        print("Tasks file was corrupted. Starting fresh.")
        return []


def save_tasks(tasks):
    """
    Save all tasks to the JSON file.
    This happens after every change so we do not lose data.
    """
    with open(TASKS_FILE, "w") as file:
        json.dump(tasks, file, indent=2)


def create_task(title, description=""):
    """
    Create a new task dictionary with all the info we need.
    Each task has: id, title, description, completed status, and creation date.
    """
    tasks = load_tasks()

    # Find the highest ID so we can create a new unique one
    max_id = 0
    for task in tasks:
        if task["id"] > max_id:
            max_id = task["id"]

    new_task = {
        "id": max_id + 1,
        "title": title,
        "description": description,
        "completed": False,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    tasks.append(new_task)
    save_tasks(tasks)

    print("Task added: " + title)
    return new_task


def list_tasks(filter_by=None):
    """
    Display all tasks, with optional filtering.
    filter_by can be: None (all tasks), "completed", or "pending"
    """
    tasks = load_tasks()

    if not tasks:
        print("No tasks yet! Add one to get started.")
        return

    # Filter tasks based on what the user wants to see
    filtered_tasks = tasks
    if filter_by == "completed":
        filtered_tasks = [t for t in tasks if t["completed"]]
    elif filter_by == "pending":
        filtered_tasks = [t for t in tasks if not t["completed"]]

    if not filtered_tasks:
        print("No " + filter_by + " tasks found.")
        return

    print("\n" + "="*70)
    print("{:<4} {:<10} {:<35} {:<15}".format("ID", "Status", "Title", "Created"))
    print("="*70)

    for task in filtered_tasks:
        # Show status: Done or TODO
        status = "Done" if task["completed"] else "TODO"
        # Shorten title if too long for the display
        title = task["title"][:34] if len(task["title"]) > 34 else task["title"]
        # Just show the date, not the time
        created = task["created_at"][:10]

        print("{:<4} {:<10} {:<35} {:<15}".format(task["id"], status, title, created))

    print("="*70 + "\n")


def complete_task(task_id):
    """
    Mark a task as done by finding it by ID and setting completed to True.
    """
    tasks = load_tasks()

    # Find the task with this ID
    task_found = False
    for task in tasks:
        if task["id"] == task_id:
            task["completed"] = True
            task_found = True
            break

    if not task_found:
        print("Task with ID " + str(task_id) + " not found.")
        return

    save_tasks(tasks)
    print("Task marked as complete!")


def delete_task(task_id):
    """
    Remove a task from the list completely.
    """
    tasks = load_tasks()

    # Create a new list without the task we want to delete
    original_count = len(tasks)
    tasks = [t for t in tasks if t["id"] != task_id]

    if len(tasks) == original_count:
        print("Task with ID " + str(task_id) + " not found.")
        return

    save_tasks(tasks)
    print("Task deleted!")


def search_tasks(keyword):
    """
    Find tasks that contain a keyword in the title or description.
    """
    tasks = load_tasks()
    keyword_lower = keyword.lower()

    # Filter tasks where keyword appears in title OR description
    matching_tasks = [
        t for t in tasks
        if keyword_lower in t["title"].lower() or
           keyword_lower in t["description"].lower()
    ]

    if not matching_tasks:
        print("No tasks found matching " + keyword)
        return

    print("\nFound " + str(len(matching_tasks)) + " task(s) matching " + keyword + ":")
    print("="*70)
    print("{:<4} {:<10} {:<35} {:<15}".format("ID", "Status", "Title", "Created"))
    print("="*70)

    for task in matching_tasks:
        status = "Done" if task["completed"] else "TODO"
        title = task["title"][:34] if len(task["title"]) > 34 else task["title"]
        created = task["created_at"][:10]
        print("{:<4} {:<10} {:<35} {:<15}".format(task["id"], status, title, created))

    print("="*70 + "\n")


# ============================================================================
# MENU INTERFACE - This is what the user sees
# ============================================================================

def show_menu():
    """
    Display the main menu and show what options are available.
    """
    print("\n" + "="*70)
    print("TASK MANAGER")
    print("="*70)
    print("1. Add a new task")
    print("2. View all tasks")
    print("3. View completed tasks")
    print("4. View pending tasks")
    print("5. Mark a task as complete")
    print("6. Delete a task")
    print("7. Search for a task")
    print("8. Exit")
    print("="*70 + "\n")


def run_app():
    """
    Main loop that keeps the app running until the user exits.
    """
    print("\nWelcome to Task Manager!")
    print("Your tasks will be saved automatically between sessions.\n")

    while True:
        show_menu()
        choice = input("Choose an option (1-8): ").strip()

        # OPTION 1: Add a new task
        if choice == "1":
            title = input("\nEnter task title: ").strip()
            if not title:
                print("Task title cannot be empty!")
                continue

            description = input("Enter task description (optional, press Enter to skip): ").strip()
            create_task(title, description)

        # OPTION 2: View all tasks
        elif choice == "2":
            print()
            list_tasks()

        # OPTION 3: View completed tasks
        elif choice == "3":
            print()
            list_tasks(filter_by="completed")

        # OPTION 4: View pending tasks
        elif choice == "4":
            print()
            list_tasks(filter_by="pending")

        # OPTION 5: Mark task as complete
        elif choice == "5":
            print()
            list_tasks()  # Show tasks so user knows the IDs
            try:
                task_id = int(input("Enter the ID of the task to complete: "))
                complete_task(task_id)
            except ValueError:
                print("Please enter a valid number!")

        # OPTION 6: Delete a task
        elif choice == "6":
            print()
            list_tasks()  # Show tasks so user knows the IDs
            try:
                task_id = int(input("Enter the ID of the task to delete: "))
                delete_task(task_id)
            except ValueError:
                print("Please enter a valid number!")

        # OPTION 7: Search for a task
        elif choice == "7":
            keyword = input("\nEnter keyword to search for: ").strip()
            if not keyword:
                print("Please enter a keyword!")
                continue
            search_tasks(keyword)

        # OPTION 8: Exit
        elif choice == "8":
            print("\nGoodbye! Your tasks have been saved.")
            break

        # Invalid choice
        else:
            print("Invalid choice. Please enter a number between 1 and 8.")


# ============================================================================
# START THE APP
# ============================================================================

if __name__ == "__main__":
    run_app()

{
    "id": 1,                                    # Unique number
    "title": "Buy groceries",                   # Task name
    "description": "Milk, eggs, bread",         # Optional details
    "completed": False,                         # True when done
    "created_at": "2024-03-20 14:30:45"        # When it was created
}