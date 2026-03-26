import json
import os
from datetime import datetime

TASKS_FILE = os.path.expanduser("~/tasks.json")

def load_tasks():
    # Load tasks from the JSON file, return empty list if file doesn't exist
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE, "r") as f:
            return json.load(f)
    return []

def save_tasks(tasks):
    # Save tasks to JSON file so they persist between sessions
    with open(TASKS_FILE, "w") as f:
        json.dump(tasks, f, indent=2)

def add_task(task_text):
    # Add a new task with automatic ID assignment
    tasks = load_tasks()
    new_id = max(t["id"] for t in tasks) + 1 if tasks else 1
    new_task = {
        "id": new_id,
        "text": task_text,
        "completed": False,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    tasks.append(new_task)
    save_tasks(tasks)
    print(f"✓ Added task #{new_id}: {task_text}")

def list_tasks(show_completed=True):
    # Display tasks, optionally filtering out completed ones
    tasks = load_tasks()
    if not tasks:
        print("No tasks yet! Add one with: add Your task")
        return
    if not show_completed:
        tasks = [t for t in tasks if not t["completed"]]
    if not tasks:
        print("No incomplete tasks!")
        return
    
    print("\n" + "="*60)
    print("YOUR TASKS")
    print("="*60)
    for task in tasks:
        status = "✓" if task["completed"] else "○"
        text = f"[DONE] {task['text']}" if task["completed"] else task['text']
        print(f"  {status} #{task['id']}: {text}")
        print(f"     Created: {task['created_at']}")
    print("="*60 + "\n")

def complete_task(task_id):
    # Mark a task as completed by ID
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task["completed"] = True
            save_tasks(tasks)
            print(f"✓ Marked task #{task_id} as completed!")
            return
    print(f"❌ Task #{task_id} not found!")

def delete_task(task_id):
    # Delete a task by ID
    tasks = load_tasks()
    orig_len = len(tasks)
    tasks = [t for t in tasks if t["id"] != task_id]
    if len(tasks) == orig_len:
        print(f"❌ Task #{task_id} not found!")
        return
    save_tasks(tasks)
    print(f"✓ Deleted task #{task_id}!")

def filter_tasks(ftype, fval):
    # Filter tasks by status or search text
    tasks = load_tasks()
    if ftype.lower() == "status":
        if fval.lower() == "completed":
            filtered = [t for t in tasks if t["completed"]]
        elif fval.lower() == "incomplete":
            filtered = [t for t in tasks if not t["completed"]]
        else:
            print("Use 'completed' or 'incomplete'")
            return
    elif ftype.lower() == "search":
        filtered = [t for t in tasks if fval.lower() in t["text"].lower()]
    else:
        print("Use 'status' or 'search'")
        return
    
    if not filtered:
        print(f"No tasks found")
        return
    print(f"\nFiltered tasks: {ftype} = {fval}")
    print("="*60)
    for task in filtered:
        status = "✓" if task["completed"] else "○"
        text = f"[DONE] {task['text']}" if task["completed"] else task['text']
        print(f"  {status} #{task['id']}: {text}")
    print("="*60 + "\n")

def main():
    # Main program loop
    print("\n🎯 Welcome to Task Manager!")
    print("   Type 'help' for commands\n")
    
    while True:
        inp = input("task> ").strip()
        if not inp:
            continue
        
        parts = inp.split(maxsplit=1)
        cmd = parts[0].lower()
        
        if cmd == "add":
            if len(parts) < 2:
                print("❌ Usage: add Your task text")
            else:
                add_task(parts[1])
        elif cmd == "list":
            list_tasks(show_completed=False)
        elif cmd == "list-all":
            list_tasks(show_completed=True)
        elif cmd == "complete":
            if len(parts) < 2:
                print("❌ Usage: complete <task_id>")
            else:
                try:
                    complete_task(int(parts[1]))
                except ValueError:
                    print("❌ Task ID must be a number")
        elif cmd == "delete":
            if len(parts) < 2:
                print("❌ Usage: delete <task_id>")
            else:
                try:
                    delete_task(int(parts[1]))
                except ValueError:
                    print("❌ Task ID must be a number")
        elif cmd == "filter":
            if len(parts) < 2:
                print("❌ Usage: filter <type> <value>")
                print("   Types: status (completed/incomplete), search (text)")
            else:
                fparts = parts[1].split(maxsplit=1)
                if len(fparts) < 2:
                    print("❌ Need both type and value")
                else:
                    filter_tasks(fparts[0], fparts[1])
        elif cmd == "help":
            print("\nCommands:")
            print("  add <text>           - Add a new task")
            print("  list                 - Show incomplete tasks")
            print("  list-all             - Show all tasks")
            print("  complete <id>        - Mark task done")
            print("  delete <id>          - Delete a task")
            print("  filter status <val>  - Filter by status")
            print("  filter search <text> - Search tasks")
            print("  quit                 - Exit")
        elif cmd in ["quit", "exit"]:
            print("👋 Goodbye!")
            break
        else:
            print(f"❌ Unknown command: {cmd}. Type 'help'")

if __name__ == "__main__":
    main()