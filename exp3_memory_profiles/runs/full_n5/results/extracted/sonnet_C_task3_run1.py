#!/usr/bin/env python3
"""tasks.py — A persistent CLI task manager. Data lives at ~/.tasks.json"""

import argparse, json, os, sys
from datetime import datetime

TASKS_FILE = os.path.expanduser("~/.tasks.json")

RESET  = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
RED    = "\033[31m"; GREEN = "\033[32m"; YELLOW = "\033[33m"; BLUE = "\033[34m"

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}
PRIORITY_COLOR = {"high": RED, "medium": YELLOW, "low": BLUE}
PRIORITY_LABEL = {"high": "high  ", "medium": "medium", "low": "low   "}


def _color_enabled():
    return sys.stdout.isatty() and not os.getenv("NO_COLOR")

def c(code, text):
    """Wrap text in ANSI escape code; skipped when piped or NO_COLOR is set."""
    return code + text + RESET if _color_enabled() else text


# ── Storage ───────────────────────────────────────────────────────────────────

def load_tasks():
    if not os.path.exists(TASKS_FILE):
        return []
    try:
        with open(TASKS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(c(RED, "Warning: could not read tasks: " + str(e)), file=sys.stderr)
        return []

def save_tasks(tasks):
    try:
        with open(TASKS_FILE, "w") as f:
            json.dump(tasks, f, indent=2)
    except OSError as e:
        print(c(RED, "Error saving tasks: " + str(e)), file=sys.stderr)
        sys.exit(1)

def next_id(tasks):
    """Monotonically increasing — never reuses IDs from deleted tasks."""
    return max((t["id"] for t in tasks), default=0) + 1


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_add(args):
    tasks = load_tasks()
    task = {
        "id":           next_id(tasks),
        "title":        args.title,
        "priority":     args.priority,
        "tags":         args.tag or [],
        "done":         False,
        "created_at":   datetime.now().isoformat(timespec="seconds"),
        "completed_at": None,
    }
    tasks.append(task)
    save_tasks(tasks)
    tag_hint = "  [" + ", ".join(task["tags"]) + "]" if task["tags"] else ""
    print(c(GREEN, "v") + " Added #" + str(task["id"]) + ": " + task["title"] + c(DIM, tag_hint))


def cmd_done(args):
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == args.id:
            if task["done"]:
                print(c(YELLOW, "Task #" + str(args.id) + " is already complete."))
                return
            task["done"] = True
            task["completed_at"] = datetime.now().isoformat(timespec="seconds")
            save_tasks(tasks)
            print(c(GREEN, "v") + " Completed #" + str(task["id"]) + ": " + task["title"])
            return
    print(c(RED, "x Task #" + str(args.id) + " not found."))
    sys.exit(1)


def cmd_delete(args):
    tasks = load_tasks()
    filtered = [t for t in tasks if t["id"] != args.id]
    if len(filtered) == len(tasks):
        print(c(RED, "x Task #" + str(args.id) + " not found."))
        sys.exit(1)
    removed = next(t for t in tasks if t["id"] == args.id)
    save_tasks(filtered)
    print(c(RED, "x") + " Deleted #" + str(args.id) + ": " + removed["title"])


def cmd_list(args):
    tasks = load_tasks()

    # Status filter
    if args.filter == "pending":
        tasks = [t for t in tasks if not t["done"]]
    elif args.filter == "done":
        tasks = [t for t in tasks if t["done"]]
    # Tag filter
    if args.tag:
        tasks = [t for t in tasks if args.tag in t.get("tags", [])]
    # Priority filter
    if args.priority:
        tasks = [t for t in tasks if t["priority"] == args.priority]

    if not tasks:
        print(c(DIM, "  No tasks match your filters."))
        return

    # Sort: pending first → by priority → by id
    tasks.sort(key=lambda t: (t["done"], PRIORITY_ORDER.get(t["priority"], 3), t["id"]))

    hdr = ("  " + "ID".rjust(4) + "  " + "PRIORITY".ljust(8) + "  "
           + "STATUS".ljust(9) + "  " + "TAGS".ljust(20) + "  TITLE")
    print()
    print(c(BOLD, hdr))
    print(c(DIM, "  " + "-" * 67))

    for t in tasks:
        tid  = str(t["id"]).rjust(4)
        prio = c(PRIORITY_COLOR.get(t["priority"], RESET), PRIORITY_LABEL.get(t["priority"], t["priority"]))
        tags = ", ".join(t.get("tags", [])) or "-"
        if t["done"]:
            status = c(GREEN,  "done     ")
            title  = c(DIM, t["title"])
        else:
            status = c(YELLOW, "pending  ")
            title  = t["title"]
        print("  " + tid + "  " + prio + "  " + status + "  " + tags.ljust(20) + "  " + title)

    total = len(tasks)
    done  = sum(1 for t in tasks if t["done"])
    pct   = int(done / total * 100) if total else 0
    print()
    print(c(DIM, "  " + str(done) + "/" + str(total) + " tasks complete (" + str(pct) + "%)"))
    print()


def cmd_stats(args):
    tasks = load_tasks()
    if not tasks:
        print(c(DIM, "  No tasks yet."))
        return
    total   = len(tasks)
    done    = sum(1 for t in tasks if t["done"])
    pending = total - done
    by_prio = {p: sum(1 for t in tasks if t["priority"] == p and not t["done"])
               for p in ("high", "medium", "low")}
    all_tags = sorted({tag for t in tasks for tag in t.get("tags", [])})

    print()
    print(c(BOLD, "  Overview"))
    print(c(DIM,  "  ---------------"))
    print("  Total      " + str(total))
    print("  " + c(GREEN, "Done") + "       " + str(done))
    print("  " + c(YELLOW, "Pending") + "    " + str(pending))
    print()
    print(c(BOLD, "  Pending by Priority"))
    print(c(DIM,  "  ---------------"))
    for prio, count in by_prio.items():
        bar   = c(PRIORITY_COLOR[prio], "#" * count) if count else c(DIM, "-")
        label = c(PRIORITY_COLOR[prio], prio.capitalize().ljust(8))
        print("  " + label + "  " + bar + "  " + str(count))
    print()
    if all_tags:
        print(c(BOLD, "  Tags in use"))
        print(c(DIM,  "  ---------------"))
        for tag in all_tags:
            n = sum(1 for t in tasks if tag in t.get("tags", []))
            print("  " + tag.ljust(20) + "  " + str(n) + " task" + ("s" if n != 1 else ""))
        print()


# ── Argument parser ───────────────────────────────────────────────────────────

def build_parser():
    parser = argparse.ArgumentParser(
        prog="tasks",
        description="A persistent command-line task manager.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    p = sub.add_parser("add", help="Add a new task")
    p.add_argument("title", help="Task title (quote multi-word titles)")
    p.add_argument("--priority", "-p", choices=["high", "medium", "low"],
                   default="medium", help="Priority (default: medium)")
    p.add_argument("--tag", "-t", action="append", metavar="TAG",
                   help="Tag — repeatable: --tag dev --tag api")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("done", help="Mark a task complete")
    p.add_argument("id", type=int, help="Task ID")
    p.set_defaults(func=cmd_done)

    p = sub.add_parser("delete", aliases=["rm"], help="Delete a task permanently")
    p.add_argument("id", type=int, help="Task ID")
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("list", aliases=["ls"], help="List tasks")
    p.add_argument("--filter", "-f", choices=["all", "pending", "done"],
                   default="all", help="Filter by status (default: all)")
    p.add_argument("--tag", "-t", metavar="TAG", help="Filter by tag")
    p.add_argument("--priority", "-p", choices=["high", "medium", "low"],
                   help="Filter by priority")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("stats", help="Show task summary")
    p.set_defaults(func=cmd_stats)

    return parser


if __name__ == "__main__":
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)