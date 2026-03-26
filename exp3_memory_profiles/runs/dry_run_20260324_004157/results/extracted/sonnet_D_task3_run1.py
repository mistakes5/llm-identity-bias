#!/usr/bin/env python3
"""task — persistent CLI task manager

Usage:
  task add "Buy milk" --tag shopping --priority high
  task done a1b2c3d4
  task ls --status pending --tag shopping
  task edit a1b2c3d4 --priority low
  task rm a1b2c3d4

Storage: $TASKS_FILE or ~/.local/share/tasks/tasks.json
"""

from __future__ import annotations

import argparse, json, os, sys, uuid
from datetime import datetime, timezone
from pathlib import Path

_DEFAULT_PATH = Path.home() / ".local" / "share" / "tasks" / "tasks.json"
TASKS_FILE    = Path(os.environ.get("TASKS_FILE", _DEFAULT_PATH))
Task          = dict
PRIORITIES    = ("low", "medium", "high")
STATUSES      = ("pending", "done")
_PRIORITY_RANK = {p: i for i, p in enumerate(PRIORITIES)}

def _load() -> list[Task]:
    if not TASKS_FILE.exists(): return []
    try:
        data = json.loads(TASKS_FILE.read_text())
    except json.JSONDecodeError as e: _die(f"corrupt task file: {e}")
    except OSError as e:              _die(f"cannot read task file: {e}")
    if not isinstance(data, list):    _die("expected JSON array")
    return data

def _save(tasks: list[Task]) -> None:
    try:
        TASKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        TASKS_FILE.write_text(json.dumps(tasks, indent=2) + "\n")
    except OSError as e: _die(f"cannot write task file: {e}")

def _die(msg: str) -> None:
    print(f"error: {msg}", file=sys.stderr); sys.exit(1)

def _now()         -> str:  return datetime.now(timezone.utc).isoformat()
def _short(tid: str) -> str: return tid[:8]

def _resolve(tasks: list[Task], prefix: str) -> Task:
    m = [t for t in tasks if t["id"].startswith(prefix)]
    if not m: _die(f"no task matches '{prefix}'")
    if len(m) > 1:
        _die(f"ambiguous '{prefix}' — matches: {', '.join(_short(t['id']) for t in m)}")
    return m[0]

# ── Filter composition (AND semantics) ───────────────────────────────────────

def _apply_filters(tasks, *, status, tag, priority) -> list[Task]:
    """
    All supplied predicates must match (AND/intersection).
    This is intentionally left for you to implement — see the TODO below.
    Swap for set-union if you prefer OR semantics.
    """
    # TODO: implement (~5-8 lines)
    #
    #   result = tasks
    #   if status:   result = [t for t in result if t["status"] == status]
    #   if tag:      result = [t for t in result if tag in t["tags"]]
    #   if priority: result = [t for t in result if t["priority"] == priority]
    #   return result
    return tasks  # passthrough until implemented

# ── Formatting ────────────────────────────────────────────────────────────────

_NC = not sys.stdout.isatty() or bool(os.environ.get("NO_COLOR"))
def _c(x): return "" if _NC else f"\033[{x}m"

_R=_c("0"); _B=_c("1"); _DIM=_c("2"); _CYN=_c("36")
_SC={"pending":_c("33"),"done":_c("32")}
_PC={"low":_c("37"),"medium":_c("33"),"high":_c("31")}

def _fmt(t):
    tags = f"  {_DIM}[{', '.join(t['tags'])}]{_R}" if t["tags"] else ""
    dim  = _DIM if t["status"] == "done" else ""
    return (f"  {_CYN}{_short(t['id'])}{_R}  "
            f"{_SC.get(t['status'],'')}{t['status']:<7}{_R}  "
            f"{_PC.get(t['priority'],'')}{t['priority']:<6}{_R}  "
            f"{dim}{t['title']}{_R}{tags}")

def _header():
    return f"\n  {_B}{'ID':<8}  {'STATUS':<7}  {'PRIO':<6}  TITLE{_R}\n  {'─'*56}"

# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_add(a):
    tasks = _load()
    t = {"id": str(uuid.uuid4()), "title": a.title, "status": "pending",
         "priority": a.priority, "tags": a.tag or [],
         "created_at": _now(), "completed_at": None}
    tasks.append(t); _save(tasks)
    print(f"added  {_CYN}{_short(t['id'])}{_R}  {t['title']}")

def cmd_done(a):
    tasks = _load(); t = _resolve(tasks, a.id)
    if t["status"] == "done":
        print(f"already done: {_short(t['id'])}  {t['title']}"); return
    t["status"] = "done"; t["completed_at"] = _now()
    _save(tasks)
    print(f"{_c('32')}done{_R}   {_short(t['id'])}  {t['title']}")

def cmd_rm(a):
    tasks = _load(); t = _resolve(tasks, a.id); tasks.remove(t); _save(tasks)
    print(f"removed  {_short(t['id'])}  {t['title']}")

def cmd_edit(a):
    tasks = _load(); t = _resolve(tasks, a.id)
    if a.title    is not None: t["title"]    = a.title
    if a.priority is not None: t["priority"] = a.priority
    if a.tag      is not None: t["tags"]     = a.tag
    _save(tasks); print(f"updated  {_short(t['id'])}  {t['title']}")

def cmd_ls(a):
    tasks = _load()
    out   = _apply_filters(tasks, status=a.status, tag=a.tag, priority=a.priority)
    if not out:
        print("no tasks" if not tasks else "no tasks match the given filters"); return
    out.sort(key=lambda t: (-_PRIORITY_RANK[t["priority"]], t["created_at"]))
    print(_header())
    for t in out: print(_fmt(t))
    p = sum(1 for t in out if t["status"] == "pending")
    print(f"\n  {_DIM}{p} pending, {len(out)-p} done  ({len(out)} shown){_R}\n")

# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(prog="task")
    s = p.add_subparsers(dest="cmd", metavar="COMMAND", required=True)

    a = s.add_parser("add");  a.add_argument("title")
    a.add_argument("--tag", action="append", metavar="TAG")
    a.add_argument("--priority", choices=PRIORITIES, default="medium")

    for cmd in ("done", "rm"):
        s.add_parser(cmd).add_argument("id")

    e = s.add_parser("edit"); e.add_argument("id")
    e.add_argument("--title"); e.add_argument("--priority", choices=PRIORITIES)
    e.add_argument("--tag", action="append", metavar="TAG")

    l = s.add_parser("ls")
    l.add_argument("--status", choices=STATUSES)
    l.add_argument("--tag", metavar="TAG")
    l.add_argument("--priority", choices=PRIORITIES)

    args = p.parse_args()
    {"add": cmd_add, "done": cmd_done, "rm": cmd_rm,
     "edit": cmd_edit, "ls": cmd_ls}[args.cmd](args)

if __name__ == "__main__":
    main()