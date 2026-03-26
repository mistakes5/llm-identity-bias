## 🎯 Key Features

### Data Model
- **Task** with: title, description, priority (low/medium/high), status, dates
- **Unique IDs**: ISO format timestamps ensure no collisions
- **Timestamps**: Auto-tracked creation, completion times

### Persistence
- **Location**: `~/.task_manager/tasks.json`
- **Format**: Human-readable JSON
- **Auto-load**: Tasks restore on every run
- **Custom storage**: `--storage /path/to/dir` for alternate location

### Filtering
- **By status**: pending or completed
- **By priority**: low, medium, high  
- **By search**: Case-insensitive title/description search
- **Combined**: Mix multiple filters

### Architecture

★ **Key Design Insights** ─────────────────────────────────────
1. **ID Strategy**: Uses ISO format timestamps as IDs. Collision-free in practice (microsecond precision), human-readable, and sortable without additional code.

2. **Dataclass Elegance**: `@dataclass` + `asdict()` makes serialization automatic. The bidirectional `to_dict()`/`from_dict()` pattern keeps data layer clean.

3. **Separation of Concerns**: TaskManager handles persistence, Task handles domain logic. CLI is completely independent — easy to swap argparse for a web framework later.

4. **Graceful Degradation**: If `tasks.json` is corrupted, it warns and starts fresh rather than crashing. File I/O errors are caught at the right layer.

────────────────────────────────────────────────────────────────

## 🚀 Advanced Usage

### Create an alias for quick access: