#!/usr/bin/env python3
"""Task manager with persistent JSON storage."""

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import List, Optional
from pathlib import Path


@dataclass
class Task:
    """Represents a single task."""
    id: int
    title: str
    description: Optional[str] = None
    status: str = "pending"  # pending, completed
    priority: str = "normal"  # low, normal, high
    tags: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        return cls(**data)

    def mark_completed(self):
        self.status = "completed"
        self.completed_at = datetime.now().isoformat()


class TaskManager:
    """Manages task operations including storage and retrieval."""

    def __init__(self, data_file: str = "~/.tasks.json"):
        self.data_file = Path(data_file).expanduser()
        self.tasks: List[Task] = []
        self._next_id = 1
        self._load_tasks()

    def _load_tasks(self):
        """Load tasks from the JSON file."""
        if self.data_file.exists():
            try:
                with open(self.data_file, "r") as f:
                    data = json.load(f)
                    self.tasks = [Task.from_dict(t) for t in data]
                    if self.tasks:
                        self._next_id = max(t.id for t in self.tasks) + 1
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load tasks: {e}")
                self.tasks = []

    def _save_tasks(self):
        """Save all tasks to the JSON file."""
        try:
            self.data_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.data_file, "w") as f:
                json.dump([t.to_dict() for t in self.tasks], f, indent=2)
        except IOError as e:
            print(f"Error saving tasks: {e}")

    def add_task(
        self,
        title: str,
        description: Optional[str] = None,
        priority: str = "normal",
        tags: Optional[List[str]] = None,
    ) -> Task:
        """Add a new task to the manager."""
        if tags is None:
            tags = []

        task = Task(
            id=self._next_id,
            title=title,
            description=description,
            priority=priority,
            tags=tags,
        )
        self._next_id += 1
        self.tasks.append(task)
        self._save_tasks()
        return task

    def complete_task(self, task_id: int) -> bool:
        """Mark a task as completed by ID."""
        for task in self.tasks:
            if task.id == task_id:
                task.mark_completed()
                self._save_tasks()
                return True
        return False

    def get_task(self, task_id: int) -> Optional[Task]:
        """Get a task by ID."""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None

    def delete_task(self, task_id: int) -> bool:
        """Delete a task by ID."""
        original_length = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.id != task_id]
        if len(self.tasks) < original_length:
            self._save_tasks()
            return True
        return False

    def get_all_tasks(self) -> List[Task]:
        """Get all tasks."""
        return self.tasks

    def filter_tasks(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> List[Task]:
        """
        Filter tasks by status, priority, and/or tags.

        TODO: Implement filtering logic here.

        Args:
            status: Filter by task status ('pending', 'completed')
            priority: Filter by priority level ('high', 'normal', 'low')
            tags: Filter by tags - matches tasks with ANY of these tags

        Returns:
            List of tasks matching the filter criteria.

        Design question to consider:
        - Should a task match if it has ANY tag (OR logic)?
        - Or should it match only if it has ALL tags (AND logic)?
        - How do you combine multiple filter types (status + priority)?
        """
        pass

    def list_tasks(self, status: Optional[str] = None) -> List[Task]:
        """Get tasks filtered by status."""
        if status is None:
            return self.tasks
        return [t for t in self.tasks if t.status == status]