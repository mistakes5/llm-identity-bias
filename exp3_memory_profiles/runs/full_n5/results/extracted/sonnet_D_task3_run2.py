#!/usr/bin/env python3
"""task.py — CLI task manager with JSON persistence."""

from __future__ import annotations
import argparse, json, sys, uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

STORE_PATH   = Path.home() / ".local" / "share" / "tasks" / "tasks.json"
PRIORITY_RANK: dict[str, int] = {"low": 0, "medium": 1, "high": 2}

def _ansi(c): return c if sys.stdout.isatty() else ""
RESET  = _ansi("\033[0m");  BOLD   = _ansi("\033[1m")
DIM    = _ansi("\033[2m");  STRIKE = _ansi("\033[9m")
RED    = _ansi("\033[91m"); YELLOW = _ansi("\033[93m"); GREEN = _ansi("\033[92m")
PRIORITY_COLOR = {"high": RED, "medium": YELLOW, "low": GREEN}

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

@dataclass
class Task:
    id: str; title: str
    status: str = "pending"; priority: str = "medium"
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=_utc_now)
    completed_at: Optional[str] = None

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})
    def to_dict(self) -> dict: return asdict(self)


class TaskStore:
    def __init__(self, path: Path = STORE_PATH) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._tasks: list[Task] = self._load()

    def _load(self) -> list[Task]:
        if not self.path.exists(): return []
        try:
            with self.path.open() as fh:
                return [Task.from_dict(d) for d in json.load(fh)]
        except (json.JSONDecodeError, TypeError) as exc:
            sys.exit(f"error: corrupted store: {exc}")

    def _save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        with tmp.open("w") as fh:
            json.dump([t.to_dict() for t in self._tasks], fh, indent=2)
        tmp.replace(self.path)  # atomic rename

    def add(self, title: str, priority: str = "medium", tags=None) -> Task:
        t = Task(id=uuid.uuid4().hex[:8], title=title, priority=priority, tags=tags or [])
        self._tasks.append(t); self._save(); return t

    def complete(self, tid: str) -> Task:
        t = self._resolve(tid); t.status = "done"; t.completed_at = _utc_now()
        self._save(); return t

    def delete(self, tid: str) -> Task:
        t = self._resolve(tid)
        self._tasks = [x for x in self._tasks if x.id != t.id]
        self._save(); return t

    def all(self) -> list[Task]: return list(self._tasks)

    def filter(
        self, *, status=None, priority=None, min_priority=None, tags=None
    ) -> list[Task]:
        """
        Return tasks matching ALL supplied criteria (AND semantics).

        TODO — implement this (~8 lines). The signature is fixed; fill the body.

        Parameters:
          status        "pending" | "done"  — exact match
          priority      "low"|"medium"|"high" — exact match
          min_priority  include tasks with priority >= this level
                        hint: PRIORITY_RANK[t.priority] >= PRIORITY_RANK[min_priority]
          tags          task must carry ALL listed tags  (AND-within-tags)

        When all args are None → return all tasks (no filtering).
        """
        raise NotImplementedError(
            "Implement TaskStore.filter() in task.py (~8 lines)."
        )

    def _resolve(self, prefix: str) -> Task:
        hits = [t for t in self._tasks if t.id.startswith(prefix)]
        if not hits: sys.exit(f"error: no task matching '{prefix}'")
        if len(hits) > 1:
            sys.exit(f"error: ambiguous '{prefix}' → {[t.id for t in hits]}")
        return hits[0]


def _fmt_task(t: Task, *, verbose=False) -> str:
    pc = PRIORITY_COLOR.get(t.priority, "")
    done = t.status == "done"
    title = f"{STRIKE}{DIM}{t.title}{RESET}" if done else t.title
    tags  = f"  {DIM}[{', '.join(t.tags)}]{RESET}" if t.tags else ""
    check = f"{GREEN}✓{RESET}" if done else f"{DIM}○{RESET}"
    line  = f"  {check}  {BOLD}{t.id}{RESET}  {title} {pc}({t.priority}){RESET}{tags}"
    if verbose:
        line += f"\n         created: {t.created_at}"
        if t.completed_at: line += f"  completed: {t.completed_at}"
    return line

def render_list(tasks: list[Task], *, verbose=False) -> None:
    if not tasks:
        print(f"\n  {DIM}No tasks.{RESET}\n"); return
    ordered = sorted(
        tasks,
        key=lambda t: (t.status != "pending", -PRIORITY_RANK.get(t.priority, 1), t.created_at),
    )
    print()
    for t in ordered: print(_fmt_task(t, verbose=verbose))
    print()
    p = sum(1 for t in tasks if t.status == "pending")
    print(f"  {DIM}{p} pending  ·  {len(tasks)-p} done{RESET}\n")


def build_parser():
    p = argparse.ArgumentParser(prog="task", description="CLI task manager")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("add");   a.add_argument("title")
    a.add_argument("-p","--priority", choices=["low","medium","high"], default="medium")
    a.add_argument("-t","--tag", dest="tags", action="append", default=[], metavar="TAG")

    d = sub.add_parser("done");   d.add_argument("id")
    x = sub.add_parser("delete", aliases=["rm"]); x.add_argument("id")

    ls = sub.add_parser("list", aliases=["ls"])
    ls.add_argument("-s","--status",   choices=["pending","done"])
    ls.add_argument("-p","--priority", choices=["low","medium","high"])
    ls.add_argument("-m","--min-priority", choices=["low","medium","high"], dest="min_priority")
    ls.add_argument("-t","--tag", dest="tags", action="append", default=[], metavar="TAG")
    ls.add_argument("-v","--verbose", action="store_true")
    return p

def main():
    args  = build_parser().parse_args()
    store = TaskStore()

    if args.cmd == "add":
        t = store.add(args.title, priority=args.priority, tags=args.tags)
        pc = PRIORITY_COLOR[t.priority]
        print(f"\n  {GREEN}+{RESET} {BOLD}{t.id}{RESET}  {t.title}  {pc}({t.priority}){RESET}\n")
    elif args.cmd == "done":
        t = store.complete(args.id)
        print(f"\n  {GREEN}✓{RESET} {BOLD}{t.id}{RESET}  {DIM}{t.title}{RESET}\n")
    elif args.cmd in ("delete","rm"):
        t = store.delete(args.id)
        print(f"\n  {RED}✗{RESET} deleted {BOLD}{t.id}{RESET}  {t.title}\n")
    elif args.cmd in ("list","ls"):
        render_list(
            store.filter(
                status=args.status, priority=args.priority,
                tags=args.tags or None, min_priority=args.min_priority,
            ),
            verbose=args.verbose,
        )

if __name__ == "__main__": main()

def filter(self, *, status=None, priority=None, min_priority=None, tags=None) -> list[Task]:
    results = self.all()

    # your implementation here — consider:
    # 1. status filter    → exact string match
    # 2. priority filter  → exact match
    # 3. min_priority     → PRIORITY_RANK[t.priority] >= PRIORITY_RANK[min_priority]
    # 4. tags filter      → AND semantics: task must have ALL listed tags
    #                       hint: set(tags).issubset(set(t.tags))

    return results