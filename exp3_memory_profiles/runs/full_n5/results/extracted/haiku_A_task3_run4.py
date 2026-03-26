## Architecture Overview

★ Insight ─────────────────────────────────────
**Layered separation of concerns**: The code uses three distinct layers—**Data Model** (Task dataclass), **Storage** (JSON persistence), and **CLI** (user interface). This separation makes the system testable and easy to extend (e.g., you could swap JSON for SQLite without touching the CLI).

**Dataclass advantages**: The `@dataclass` decorator auto-generates `__init__`, `__repr__`, and the `to_dict()`/`from_dict()` pair makes JSON serialization trivial and less error-prone than manual dict handling.
─────────────────────────────────────────────────

## Features Implemented

✅ **Add tasks** with optional descriptions and tags
✅ **Complete tasks** and track completion time
✅ **Delete tasks** 
✅ **List tasks** with rich formatting (status icons, tags, descriptions)
✅ **Filter by status** (pending/completed)
✅ **Filter by date** (created today)
✅ **Filter by tag** (any task can have multiple tags)
✅ **Persistent storage** in `~/.task_manager/tasks.json`
✅ **Auto-incrementing IDs** for each task
✅ **Error handling** for missing tasks and invalid input

## Storage Format

Tasks are stored in `~/.task_manager/tasks.json`. Here's an example: