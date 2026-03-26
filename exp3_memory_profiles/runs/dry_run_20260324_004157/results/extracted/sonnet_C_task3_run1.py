#!/usr/bin/env python3
"""
tasks.py — Persistent command-line task manager.

Usage
-----
  python tasks.py add "Buy groceries" --priority high --tags shopping,errands
  python tasks.py list
  python tasks.py list --status all --priority high
  python tasks.py list --tag shopping
  python tasks.py done 3 5
  python tasks.py delete 2
  python tasks.py clear --done

Storage: ~/.tasks.json
"""

from __future__ import annotations
import json, argparse, sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── ANSI helpers ───────────────────────────────────────────────────────────────
RESET  = "\033[0m";  BOLD = "\033[1m";  DIM  = "\033[2m"
RED    = "\033[91m"; GREEN = "\033[92m"; YELLOW = "\033[93m"
CYAN   = "\033[96m"; GREY  = "\033[90m"

def clr(text, *codes): return "".join(codes) + str(text) + RESET

# ── Data model ─────────────────────────────────────────────────────────────────
PRIORITY_ORDER  = {"high": 0, "medium": 1, "low": 2}
PRIORITY_COLOUR = {"high": RED, "medium": YELLOW, "low": CYAN}

@dataclass
class Task:
    id:           int
    title:        str
    status:       str       = "pending"
    priority:     str       = "medium"
    tags:         list[str] = field(default_factory=list)
    created_at:   str       = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    def age(self) -> str:
        delta = datetime.now() - datetime.fromisoformat(self.created_at)
        if delta.days >= 1:   return f"{delta.days}d ago"
        h = delta.seconds // 3600
        if h >= 1:            return f"{h}h ago"
        m = delta.seconds // 60
        return f"{m}m ago" if m >= 1 else "just now"

# ── Storage ────────────────────────────────────────────────────────────────────
STORAGE_PATH = Path.home() / ".tasks.json"

class TaskManager:
    def __init__(self, path: Path = STORAGE_PATH):
        self.path = path; self.tasks: list[Task] = []; self._next_id = 1
        self._load()

    def _load(self) -> None:
        if not self.path.exists(): return
        try:
            raw = json.loads(self.path.read_text())
            self.tasks    = [Task(**t) for t in raw.get("tasks", [])]
            self._next_id = raw.get("next_id", 1)
        except (json.JSONDecodeError, TypeError, KeyError):
            print(clr("Warning: corrupt task file — starting fresh.", YELLOW), file=sys.stderr)

    def _save(self) -> None:
        self.path.write_text(json.dumps({"next_id": self._next_id,
                                         "tasks": [asdict(t) for t in self.tasks]}, indent=2))

    def add(self, title: str, priority: str = "medium", tags: list[str] | None = None) -> Task:
        task = Task(id=self._next_id, title=title, priority=priority, tags=tags or [])
        self.tasks.append(task); self._next_id += 1; self._save(); return task

    def complete(self, *ids: int) -> list[Task]:
        done = []
        for tid in ids:
            t = self._by_id(tid)
            if t and t.status != "done":
                t.status = "done"; t.completed_at = datetime.now().isoformat(); done.append(t)
        if done: self._save()
        return done

    def delete(self, *ids: int) -> list[Task]:
        removed = []
        for tid in ids:
            t = self._by_id(tid)
            if t: self.tasks.remove(t); removed.append(t)
        if removed: self._save()
        return removed

    def clear_done(self) -> int:
        before = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.status != "done"]; self._save()
        return before - len(self.tasks)

    def _by_id(self, tid: int) -> Optional[Task]:
        return next((t for t in self.tasks if t.id == tid), None)

    def filter(self, status=None, priority=None, tag=None) -> list[Task]:
        r = self.tasks[:]
        if status and status != "all":  r = [t for t in r if t.status == status]
        if priority:                    r = [t for t in r if t.priority == priority]
        if tag: r = [t for t in r if tag.lower() in [tg.lower() for tg in t.tags]]
        # pending first → priority order → oldest first
        r.sort(key=lambda t: (t.status == "done",
                               PRIORITY_ORDER.get(t.priority, 1),
                               t.created_at))
        return r

# ── Display ────────────────────────────────────────────────────────────────────
def format_task(task: Task) -> str:
    if task.status == "done":
        ind, title = clr("✓", GREEN), clr(task.title, DIM)
    else:
        pc = PRIORITY_COLOUR.get(task.priority, RESET)
        ind, title = clr("○", pc), clr(task.title, BOLD)

    pc    = PRIORITY_COLOUR.get(task.priority, RESET)
    ptag  = clr(f"[{task.priority:6}]", pc)
    tags  = ("  " + " ".join(clr(f"#{tg}", CYAN) for tg in task.tags)) if task.tags else ""
    return f"  {ind}  {clr(f'#{task.id:<3}', GREY)}  {ptag}  {title}{tags}  {clr(task.age(), GREY)}"

def print_tasks(tasks: list[Task], heading: str = "") -> None:
    if heading: print(f"\n{clr(heading, BOLD, CYAN)}")
    if not tasks: print(clr("  No tasks found.", GREY))
    else:
        print()
        for t in tasks: print(format_task(t))
    print()

# ── CLI ────────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    p   = argparse.ArgumentParser(prog="tasks", description="Persistent command-line task manager")
    sub = p.add_subparsers(dest="command", metavar="COMMAND"); sub.required = True

    ap = sub.add_parser("add",    help="Add a new task")
    ap.add_argument("title")
    ap.add_argument("-p", "--priority", choices=["high","medium","low"], default="medium")
    ap.add_argument("-t", "--tags",     help="Comma-separated tags")

    dp = sub.add_parser("done",   help="Mark task(s) complete")
    dp.add_argument("ids", nargs="+", type=int, metavar="ID")

    rp = sub.add_parser("delete", aliases=["rm"], help="Delete task(s)")
    rp.add_argument("ids", nargs="+", type=int, metavar="ID")

    lp = sub.add_parser("list",   aliases=["ls"], help="List tasks")
    lp.add_argument("-s", "--status",   choices=["pending","done","all"], default="pending")
    lp.add_argument("-p", "--priority", choices=["high","medium","low"])
    lp.add_argument("-t", "--tag",      help="Filter by tag")

    cp = sub.add_parser("clear",  help="Bulk-remove tasks")
    cp.add_argument("--done", action="store_true", help="Remove all completed tasks")
    return p

def main() -> None:
    args = build_parser().parse_args()
    mgr  = TaskManager()
    cmd  = args.command

    if cmd == "add":
        tags = [t.strip() for t in args.tags.split(",")] if args.tags else []
        t    = mgr.add(args.title, priority=args.priority, tags=tags)
        pc   = PRIORITY_COLOUR.get(t.priority, RESET)
        print(f"\n  {clr('✓ Added', GREEN)}  {clr(f'#{t.id}', GREY)}  "
              f"{clr(t.title, BOLD)}  {clr(f'[{t.priority}]', pc)}\n")

    elif cmd == "done":
        completed = mgr.complete(*args.ids); done_ids = {t.id for t in completed}
        for t in completed:
            print(f"\n  {clr('✓ Done', GREEN)}  {clr(f'#{t.id}', GREY)}  {clr(t.title, DIM)}")
        for tid in args.ids:
            if tid not in done_ids: print(f"  {clr(f'✗ #{tid} not found or already done', YELLOW)}")
        print()

    elif cmd in ("delete", "rm"):
        removed = mgr.delete(*args.ids); removed_ids = {t.id for t in removed}
        for t in removed:
            print(f"\n  {clr('✗ Deleted', RED)}  {clr(f'#{t.id}', GREY)}  {t.title}")
        for tid in args.ids:
            if tid not in removed_ids: print(f"  {clr(f'✗ #{tid} not found', YELLOW)}")
        print()

    elif cmd in ("list", "ls"):
        tasks   = mgr.filter(status=args.status, priority=args.priority, tag=args.tag)
        heading = f"Tasks — {args.status.capitalize() if args.status != 'all' else 'All'}"
        if getattr(args, "priority", None): heading += f" / {args.priority}"
        if getattr(args, "tag",      None): heading += f" / #{args.tag}"
        print_tasks(tasks, heading)
        done_ct = sum(1 for t in mgr.tasks if t.status == "done")
        print(clr(f"  {done_ct}/{len(mgr.tasks)} completed\n", GREY))

    elif cmd == "clear":
        if args.done:
            n = mgr.clear_done()
            print(f"\n  {clr(f'✓ Cleared {n} completed task(s)', GREEN)}\n")
        else:
            print(clr("  Use --done to clear all completed tasks.", YELLOW))

if __name__ == "__main__":
    main()

r.sort(key=lambda t: (t.status == "done",
                       PRIORITY_ORDER.get(t.priority, 1),
                       t.created_at))