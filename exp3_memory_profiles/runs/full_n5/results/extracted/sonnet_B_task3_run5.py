#!/usr/bin/env python3
"""
task_manager.py — A command-line task manager with persistence.

Usage:
  python task_manager.py add "Buy groceries" -p high -t shopping food
  python task_manager.py list
  python task_manager.py list -s pending -p high
  python task_manager.py list -t shopping
  python task_manager.py complete abc12345
  python task_manager.py delete abc12345
"""
# ... (full file above)

def filter_tasks(tasks, status, priority, tag):
    result = list(tasks)
    if status:   result = [t for t in result if t.status == status]
    if priority: result = [t for t in result if t.priority == priority]
    if tag:      result = [t for t in result if tag.lower() in t.tags]
    return result

def filter_tasks(tasks, status, priority, tag):
    if not any([status, priority, tag]):
        return list(tasks)
    def matches(t):
        if status   and t.status == status:       return True
        if priority and t.priority == priority:   return True
        if tag      and tag.lower() in t.tags:    return True
        return False
    return [t for t in tasks if matches(t)]