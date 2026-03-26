#!/usr/bin/env python3
"""
task_manager — A persistent CLI task manager.

Usage:
    python task_manager.py add "Write report" --priority high --tags work,writing
    python task_manager.py list [--all]
    python task_manager.py done 3
    python task_manager.py remove 3
    python task_manager.py filter --priority high --tags work --query "report"

Storage: ~/.tasks.json  (override with $TASKS_FILE env var)
"""

import argparse, json, os, sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


# ── Constants ──────────────────────────────────────────────────────────────────

class Priority:
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"
    ALL    = ("low", "medium", "high")

class Status:
    PENDING = "pending"
    DONE    = "done"


# ── Data Model ─────────────────────────────────────────────────────────────────

@dataclass
class Task:
    id:           int
    title:        str
    priority:     str           = Priority.MEDIUM
    tags:         list[str]     = field(default_factory=list)
    status:       str           = Status.PENDING
    notes:        str           = ""
    created_at:   str           = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    def complete(self) -> None:
        self.status       = Status.DONE
        self.completed_at = datetime.now().isoformat()

    @property
    def is_done(self) -> bool:
        return self.status == Status.DONE


# ── Persistence ────────────────────────────────────────────────────────────────

class TaskStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> list[Task]:
        if not self.path.exists():
            return []
        try:
            with self.path.open() as f:
                rows = json.load(f)
            return [Task(**row) for row in rows]
        except (json.JSONDecodeError, TypeError) as exc:
            print(f"  ⚠  Could not read {self.path}: {exc}", file=sys.stderr)
            return []

    def save(self, tasks: list[Task]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w") as f:
            json.dump([asdict(t) for t in tasks], f, indent=2)


# ── Business Logic ─────────────────────────────────────────────────────────────

class TaskManager:
    def __init__(self, store: TaskStore) -> None:
        self.store = store
        self.tasks = store.load()

    def add(self, title, priority=Priority.MEDIUM, tags=None, notes="") -> Task:
        task = Task(id=self._next_id(), title=title,
                    priority=priority, tags=tags or [], notes=notes)
        self.tasks.append(task)
        self.store.save(self.tasks)
        return task

    def complete(self, task_id: int) -> Task:
        task = self._get_or_raise(task_id)
        if task.is_done:
            raise ValueError(f"Task #{task_id} is already complete.")
        task.complete()
        self.store.save(self.tasks)
        return task

    def remove(self, task_id: int) -> Task:
        task = self._get_or_raise(task_id)
        self.tasks = [t for t in self.tasks if t.id != task_id]
        self.store.save(self.tasks)
        return task

    # ── filter ──────────────────────────────────────────────────────────────────
    #
    # TODO: Your implementation goes here (5–10 lines).
    #
    # All criteria compose as AND — a task must satisfy every condition provided.
    #
    # Parameters:
    #   status   — "pending" or "done"
    #   priority — "low", "medium", or "high"
    #   tags     — list of tag strings
    #   query    — substring to find in task.title or task.notes
    #
    # Key design decisions:
    #   • Tag semantics: ANY one tag must match (OR) vs ALL tags must match (AND)?
    #   • Text search: case-sensitive or lowercase-normalised?
    #   • Partial matching: should "rep" find "report"? (almost always yes)
    #
    # Scaffold:
    #   results = list(self.tasks)
    #   if status:   results = [t for t in results if t.status == status]
    #   if priority: results = [t for t in results if t.priority == priority]
    #   if tags:     results = [t for t in results if any(tag in t.tags for tag in tags)]
    #   if query:
    #       q = query.lower()
    #       results = [t for t in results if q in t.title.lower() or q in t.notes.lower()]
    #   return results
    #
    def filter(self, status=None, priority=None, tags=None, query=None) -> list[Task]:
        raise NotImplementedError("filter() not yet implemented — see TODO above.")

    def _next_id(self) -> int:
        return max((t.id for t in self.tasks), default=0) + 1

    def _get_or_raise(self, task_id: int) -> Task:
        for t in self.tasks:
            if t.id == task_id:
                return t
        raise ValueError(f"Task #{task_id} not found.")


# ── Display ────────────────────────────────────────────────────────────────────

R  = "\033[0m";  B  = "\033[1m";  D  = "\033[2m";  S = "\033[9m"
GR = "\033[92m"; CY = "\033[96m"; RD = "\033[91m"; YL = "\033[93m"

_PRI_META  = {Priority.HIGH: ("▲", RD), Priority.MEDIUM: ("●", YL), Priority.LOW: ("▼", GR)}
_PRI_ORDER = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}

def _render(task: Task) -> str:
    g, c = _PRI_META.get(task.priority, ("●", ""))
    chk  = f"{GR}✓{R}" if task.is_done else "○"
    ttl  = f"{D}{S}{task.title}{R}" if task.is_done else task.title
    tags = ("  " + "  ".join(f"{CY}#{t}{R}" for t in task.tags)) if task.tags else ""
    date = f"  {D}{datetime.fromisoformat(task.created_at).strftime('%b %d, %H:%M')}{R}"
    line = f"  {chk} {B}#{task.id:<3}{R}  {ttl}  {c}{g} {task.priority}{R}{tags}{date}"
    if task.notes:
        line += f"\n        {D}{task.notes}{R}"
    return line

def render_list(tasks: list[Task], heading: str = "Tasks") -> None:
    if not tasks:
        print(f"\n  {D}No tasks.{R}\n"); return
    pending = sorted([t for t in tasks if not t.is_done],
                     key=lambda t: _PRI_ORDER.get(t.priority, 99))
    done    = [t for t in tasks if t.is_done]
    n       = len(tasks)
    print(f"\n  {B}{heading}{R}  {D}({n} task{'s' if n != 1 else ''}){R}")
    print(f"  {'─' * 60}")
    for t in pending: print(_render(t))
    if done:
        print(f"\n  {D}Completed{R}")
        for t in done: print(_render(t))
    print()


# ── CLI ────────────────────────────────────────────────────────────────────────

def _build_parser():
    p = argparse.ArgumentParser(prog="tasks",
        description="A fast, persistent CLI task manager.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python task_manager.py add 'Buy milk' -p low -t errands\n"
            "  python task_manager.py list\n"
            "  python task_manager.py done 1\n"
            "  python task_manager.py filter -p high -t work\n"
            "  python task_manager.py filter -q 'report'\n"
        ))
    s = p.add_subparsers(dest="command", metavar="COMMAND")

    a = s.add_parser("add",  help="Add a task")
    a.add_argument("title")
    a.add_argument("--priority", "-p", choices=Priority.ALL,
                   default=Priority.MEDIUM, metavar="{low,medium,high}")
    a.add_argument("--tags",  "-t", default="", help="Comma-separated tags")
    a.add_argument("--notes", "-n", default="", help="Short note")

    d = s.add_parser("done", help="Mark a task complete")
    d.add_argument("id", type=int)

    r = s.add_parser("remove", aliases=["rm"], help="Delete a task")
    r.add_argument("id", type=int)

    l = s.add_parser("list", aliases=["ls"], help="List tasks")
    l.add_argument("--all", "-a", action="store_true", help="Include completed")

    f = s.add_parser("filter", help="Search and filter tasks")
    f.add_argument("--status",   "-s", choices=[Status.PENDING, Status.DONE])
    f.add_argument("--priority", "-p", choices=Priority.ALL, metavar="{low,medium,high}")
    f.add_argument("--tags",     "-t", help="Comma-separated tags")
    f.add_argument("--query",    "-q", help="Substring in title or notes")
    return p

def _tags(raw): return [t.strip() for t in raw.split(",") if t.strip()]

def main():
    store   = TaskStore(Path(os.environ.get("TASKS_FILE", Path.home() / ".tasks.json")))
    manager = TaskManager(store)
    parser  = _build_parser()
    args    = parser.parse_args()

    if args.command == "add":
        t = manager.add(args.title, args.priority, _tags(args.tags), args.notes)
        print(f"\n  {GR}✓{R} Added {B}#{t.id}{R}: {t.title}\n")

    elif args.command == "done":
        try:
            t = manager.complete(args.id)
            print(f"\n  {GR}✓{R} Completed {B}#{t.id}{R}: {t.title}\n")
        except ValueError as e:
            print(f"\n  ✗ {e}\n", file=sys.stderr); sys.exit(1)

    elif args.command in ("remove", "rm"):
        try:
            t = manager.remove(args.id)
            print(f"\n  Removed #{t.id}: {t.title}\n")
        except ValueError as e:
            print(f"\n  ✗ {e}\n", file=sys.stderr); sys.exit(1)

    elif args.command in ("list", "ls"):
        tasks = manager.tasks if args.all else [t for t in manager.tasks if not t.is_done]
        render_list(tasks, "All Tasks" if args.all else "Pending Tasks")

    elif args.command == "filter":
        try:
            results = manager.filter(
                status=args.status, priority=args.priority,
                tags=_tags(args.tags) if args.tags else None, query=args.query)
            render_list(results, "Filtered Tasks")
        except NotImplementedError as e:
            print(f"\n  ✗ {e}\n", file=sys.stderr); sys.exit(1)

    else:
        parser.print_help()

if __name__ == "__main__":
    main()

def filter(self, status=None, priority=None, tags=None, query=None) -> list[Task]:
    results = list(self.tasks)
    if status:
        results = [t for t in results if t.status == status]
    if priority:
        results = [t for t in results if t.priority == priority]
    if tags:
        # ANY-match: task needs at least one tag from the filter list
        results = [t for t in results if any(tag in t.tags for tag in tags)]
    if query:
        q = query.lower()
        results = [t for t in results if q in t.title.lower() or q in t.notes.lower()]
    return results