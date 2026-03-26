#!/usr/bin/env python3
"""
tasks.py — Command-line task manager with JSON persistence.

Usage:
  python tasks.py add "Buy groceries" -p high -t shopping,personal
  python tasks.py list
  python tasks.py list --status pending --priority high
  python tasks.py list --tag shopping
  python tasks.py done 3
  python tasks.py delete 3
  python tasks.py stats
"""

import json
import argparse
import sys
from datetime import datetime
from pathlib import Path

# ── Storage ──────────────────────────────────────────────────────────────────

DATA_FILE = Path.home() / ".local" / "share" / "tasks" / "tasks.json"

def load_data() -> dict:
    if not DATA_FILE.exists():
        return {"tasks": [], "next_id": 1}
    with open(DATA_FILE, encoding="utf-8") as f:
        return json.load(f)

def save_data(data: dict) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ── Display helpers ───────────────────────────────────────────────────────────

_USE_COLOR = sys.stdout.isatty()

def _c(code): return code if _USE_COLOR else ""

RESET  = _c("\033[0m");  BOLD   = _c("\033[1m");  DIM    = _c("\033[2m")
RED    = _c("\033[91m"); YELLOW = _c("\033[93m"); BLUE   = _c("\033[94m")
GREEN  = _c("\033[92m"); CYAN   = _c("\033[96m")

PRIORITY_COLOR = {"high": RED, "medium": YELLOW, "low": BLUE}

def _priority_label(p):
    return f"{PRIORITY_COLOR.get(p,'')}{p:<6}{RESET}"

def format_task(task):
    done  = task["status"] == "done"
    icon  = f"{GREEN}✓{RESET}" if done else f"{CYAN}○{RESET}"
    title = f"{DIM}{task['title']}{RESET}" if done else f"{BOLD}{task['title']}{RESET}"
    tags  = f"  {DIM}[{', '.join(task['tags'])}]{RESET}" if task["tags"] else ""
    ts    = task["completed_at"] if done else task["created_at"]
    ts_label = "completed" if done else "created"
    line1 = f"  {icon}  {DIM}#{task['id']:<3}{RESET}  {title}"
    line2 = f"       priority={_priority_label(task['priority'])}{tags}  {DIM}{ts_label} {ts}{RESET}"
    return line1 + "\n" + line2

# ── Sort (your turn!) ─────────────────────────────────────────────────────────

def sort_tasks(tasks: list[dict]) -> list[dict]:
    """
    Return tasks in display order.

    Three strategies to consider:
      A) Urgency-first  — pending before done, high priority first, oldest first within tie
         key=lambda t: (t["status"]=="done", -PRIORITY_RANK[t["priority"]], t["created_at"])

      B) Chronological  — created_at ascending, done tasks last
         key=lambda t: (t["status"]=="done", t["created_at"])

      C) Hybrid         — pending by priority desc, done by completed_at desc (newest archive first)
         (requires a small conditional — see comment below)

    Implement your chosen strategy (5–10 lines).
    """
    PRIORITY_RANK = {"high": 3, "medium": 2, "low": 1}

    # ← Replace this with your preferred sort strategy
    return sorted(
        tasks,
        key=lambda t: (
            t["status"] == "done",
            -PRIORITY_RANK.get(t["priority"], 0),
            t["created_at"],
        ),
    )

# ── Filter ────────────────────────────────────────────────────────────────────

def filter_tasks(tasks, status=None, priority=None, tag=None):
    """AND logic — every specified filter must match."""
    result = tasks
    if status:   result = [t for t in result if t["status"] == status]
    if priority: result = [t for t in result if t["priority"] == priority]
    if tag:      result = [t for t in result if tag in t["tags"]]
    return result

# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_add(args):
    data = load_data()
    tags = [t.strip() for t in args.tags.split(",")] if args.tags else []
    task = {
        "id": data["next_id"], "title": args.title, "priority": args.priority,
        "tags": tags, "status": "pending",
        "created_at": datetime.now().isoformat(timespec="seconds"), "completed_at": None,
    }
    data["tasks"].append(task)
    data["next_id"] += 1
    save_data(data)
    print(f"{GREEN}✓{RESET} Added task {BOLD}#{task['id']}{RESET}: {task['title']}")

def cmd_done(args):
    data = load_data()
    for task in data["tasks"]:
        if task["id"] == args.id:
            if task["status"] == "done":
                print(f"Task #{args.id} is already complete."); return
            task["status"] = "done"
            task["completed_at"] = datetime.now().isoformat(timespec="seconds")
            save_data(data)
            print(f"{GREEN}✓{RESET} Completed task {BOLD}#{args.id}{RESET}: {task['title']}")
            return
    print(f"{RED}✗{RESET} Task #{args.id} not found.", file=sys.stderr); sys.exit(1)

def cmd_delete(args):
    data = load_data()
    before = len(data["tasks"])
    data["tasks"] = [t for t in data["tasks"] if t["id"] != args.id]
    if len(data["tasks"]) == before:
        print(f"{RED}✗{RESET} Task #{args.id} not found.", file=sys.stderr); sys.exit(1)
    save_data(data)
    print(f"{YELLOW}✗{RESET} Deleted task #{args.id}")

def cmd_list(args):
    data = load_data()
    tasks = sort_tasks(filter_tasks(data["tasks"], args.status, args.priority, args.tag))
    if not tasks:
        filters = ", ".join(filter(None, [
            f"status={args.status}" if args.status else None,
            f"priority={args.priority}" if args.priority else None,
            f"tag={args.tag}" if args.tag else None,
        ]))
        print(f"No tasks match: {filters}" if filters else 'No tasks yet. Try: python tasks.py add "My first task"')
        return
    pending = sum(1 for t in tasks if t["status"] == "pending")
    done    = sum(1 for t in tasks if t["status"] == "done")
    print(f"\n  {BOLD}Tasks{RESET}  {DIM}{pending} pending · {done} done · {len(tasks)} total{RESET}")
    print(f"  {'─' * 52}")
    for task in tasks: print(format_task(task))
    print()

def cmd_stats(args):
    data = load_data()
    tasks = data["tasks"]
    if not tasks: print("No tasks yet."); return
    total = len(tasks); done = sum(1 for t in tasks if t["status"] == "done")
    by_pri = {p: sum(1 for t in tasks if t["status"]=="pending" and t["priority"]==p)
              for p in ("high","medium","low")}
    all_tags: dict[str,int] = {}
    for t in tasks:
        for tag in t.get("tags",[]): all_tags[tag] = all_tags.get(tag,0)+1
    print(f"\n  {BOLD}Task Summary{RESET}\n  {'─'*30}")
    print(f"  Total    {BOLD}{total}{RESET}\n  Pending  {CYAN}{total-done}{RESET}\n  Done     {GREEN}{done}{RESET}")
    if any(by_pri.values()):
        print(f"\n  Pending by priority:")
        for p,n in by_pri.items():
            if n: print(f"    {_priority_label(p)} {n}")
    if all_tags:
        top = sorted(all_tags.items(), key=lambda x:-x[1])[:5]
        print(f"\n  Top tags:  {DIM}{'  '.join(f'{t}({n})' for t,n in top)}{RESET}")
    print()

# ── CLI wiring ────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(prog="tasks", description="CLI task manager",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Examples:\n  python tasks.py add "Write tests" -p high -t dev\n  python tasks.py list --tag dev\n  python tasks.py done 1')
    sub = p.add_subparsers(dest="command", required=True, metavar="command")

    pa = sub.add_parser("add", help="Add a task")
    pa.add_argument("title"); pa.add_argument("-p","--priority",choices=["low","medium","high"],default="medium")
    pa.add_argument("-t","--tags",metavar="TAG[,TAG]"); pa.set_defaults(func=cmd_add)

    pd = sub.add_parser("done", help="Complete a task")
    pd.add_argument("id",type=int); pd.set_defaults(func=cmd_done)

    pr = sub.add_parser("delete", aliases=["rm"], help="Delete a task")
    pr.add_argument("id",type=int); pr.set_defaults(func=cmd_delete)

    pl = sub.add_parser("list", aliases=["ls"], help="List tasks")
    pl.add_argument("--status",choices=["pending","done"])
    pl.add_argument("--priority",choices=["low","medium","high"])
    pl.add_argument("--tag"); pl.set_defaults(func=cmd_list)

    ps = sub.add_parser("stats", help="Show summary"); ps.set_defaults(func=cmd_stats)

    args = p.parse_args()
    args.func(args)

if __name__ == "__main__":
    main()

def sort_tasks(tasks: list[dict]) -> list[dict]:
    PRIORITY_RANK = {"high": 3, "medium": 2, "low": 1}

    # Strategy A — urgency-first (current):
    # pending → high priority → oldest first
    return sorted(tasks, key=lambda t: (
        t["status"] == "done",
        -PRIORITY_RANK.get(t["priority"], 0),
        t["created_at"],
    ))

    # Strategy B — chronological (swap in if you prefer):
    # pending first, then created_at ascending
    return sorted(tasks, key=lambda t: (t["status"] == "done", t["created_at"]))

    # Strategy C — hybrid (pending by priority, done by newest-completed):
    return sorted(tasks, key=lambda t: (
        t["status"] == "done",
        -PRIORITY_RANK.get(t["priority"], 0) if t["status"] == "pending"
            else t["completed_at"],
    ))