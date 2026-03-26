#!/usr/bin/env python3
"""
Command-Line Task Manager with file persistence
Supports: add, complete, list, filter, and search tasks
"""

import json
import os
from datetime import datetime
from typing import List, Dict

TASKS_FILE = "tasks.json"


class Task:
    """Represents a single task"""

    def __init__(self, title: str, task_id: int):
        self.id = task_id
        self.title = title
        self.completed = False
        self.created_at = datetime.now().strftime("%Y-%m-%d %H:%M")

    def mark_complete(self):
        """Mark task as done"""
        self.completed = True

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON storage"""
        return {
            "id": self.id,
            "title": self.title,
            "completed": self.completed,
            "created_at": self.created_at
        }

    @staticmethod
    def from_dict(data: Dict):
        """Create Task from dictionary (when loading)"""
        task = Task(data["title"], data["id"])
        task.completed = data["completed"]
        task.created_at = data["created_at"]
        return task

    def __str__(self) -> str:
        status = "X" if self.completed else " "
        return f"[{status}] #{self.id}: {self.title} ({self.created_at})"


class TaskManager:
    """Manages all task operations"""

    def __init__(self):
        self.tasks: List[Task] = []
        self.next_id = 1
        self.load_tasks()

    def load_tasks(self):
        """Load tasks from JSON file"""
        if os.path.exists(TASKS_FILE):
            try:
                with open(TASKS_FILE, "r") as f:
                    data = json.load(f)
                    self.tasks = [Task.from_dict(t) for t in data]
                    if self.tasks:
                        self.next_id = max(t.id for t in self.tasks) + 1
                print(f"✓ Loaded {len(self.tasks)} tasks")
            except json.JSONDecodeError:
                print("Could not load tasks")

    def save_tasks(self):
        """Save all tasks to JSON file"""
        with open(TASKS_FILE, "w") as f:
            json.dump([t.to_dict() for t in self.tasks], f, indent=2)

    def add_task(self, title: str):
        """Add a new task"""
        task = Task(title, self.next_id)
        self.tasks.append(task)
        self.next_id += 1
        self.save_tasks()
        print(f"✓ Added: {task}")

    def complete_task(self, task_id: int):
        """Mark task as completed"""
        for task in self.tasks:
            if task.id == task_id:
                task.mark_complete()
                self.save_tasks()
                print(f"✓ Done: {task}")
                return
        print(f"✗ Task #{task_id} not found")

    def list_tasks(self, status: str = "all"):
        """List tasks filtered by status"""
        filtered = self.tasks
        if status == "pending":
            filtered = [t for t in self.tasks if not t.completed]
        elif status == "completed":
            filtered = [t for t in self.tasks if t.completed]

        if not filtered:
            print(f"No {status} tasks")
            return

        print(f"\n--- {status.upper()} ({len(filtered)}) ---")
        for task in filtered:
            print(task)
        print()

    def search_tasks(self, keyword: str):
        """Find tasks by keyword"""
        results = [t for t in self.tasks if keyword.lower() in t.title.lower()]
        if not results:
            print(f"No tasks found with '{keyword}'")
            return

        print(f"\n--- SEARCH: '{keyword}' ({len(results)}) ---")
        for task in results:
            print(task)
        print()

    def delete_task(self, task_id: int):
        """Delete a task"""
        for i, task in enumerate(self.tasks):
            if task.id == task_id:
                deleted = self.tasks.pop(i)
                self.save_tasks()
                print(f"✓ Deleted: {deleted.title}")
                return
        print(f"✗ Task #{task_id} not found")


def show_menu():
    print("\n=== TASK MANAGER ===")
    print("(a) Add task     (c) Complete    (l) List all")
    print("(p) Pending      (d) Done        (s) Search")
    print("(r) Remove       (q) Quit\n")


def main():
    manager = TaskManager()

    while True:
        show_menu()
        choice = input("Enter command: ").lower().strip()

        if choice == "a":
            title = input("Task description: ").strip()
            if title:
                manager.add_task(title)

        elif choice == "c":
            try:
                task_id = int(input("Task ID: "))
                manager.complete_task(task_id)
            except ValueError:
                print("Please enter a valid ID")

        elif choice == "l":
            manager.list_tasks("all")

        elif choice == "p":
            manager.list_tasks("pending")

        elif choice == "d":
            manager.list_tasks("completed")

        elif choice == "s":
            keyword = input("Search keyword: ").strip()
            if keyword:
                manager.search_tasks(keyword)

        elif choice == "r":
            try:
                task_id = int(input("Task ID: "))
                manager.delete_task(task_id)
            except ValueError:
                print("Please enter a valid ID")

        elif choice == "q":
            print("Goodbye!")
            break

        else:
            print("Invalid command")


if __name__ == "__main__":
    main()