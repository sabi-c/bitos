# Task & Reminder System Overhaul

**Date:** 2026-03-17
**Status:** Design proposal

---

## Current State Assessment

### What exists today

**Server side (`server/`):**
- `integrations/vikunja_adapter.py` — REST adapter for Vikunja task management (currently in **mock mode**, no VIKUNJA_API_TOKEN set). Supports: `list_tasks`, `create_task`, `complete_task`, `get_today_tasks`.
- `agent_tools.py` — Three task tools: `create_task` (title + optional description/due_date), `complete_task` (by id), `get_tasks` (filter: today/all/overdue). All proxy through Vikunja adapter.
- `heartbeat.py` — Proactive system with `task_reminders` action (every 4 hours, checks overdue tasks via Vikunja, broadcasts via `/ws/proactive`).
- `main.py` — Single endpoint `GET /tasks/today` that returns Vikunja tasks.
- No Things 3 integration. The IMPLEMENTATION_PLAN mentions "Things integration" for Phase 3, but Vikunja was implemented instead. The ai-agent-env project has a Things MCP bridge but it was not ported to BITOS.

**Device side (`device/`):**
- `screens/panels/tasks.py` — TasksPanel fetches from `GET /tasks/today`, caches locally, shows list with cursor navigation. Double-press marks complete (in-place, no server call).
- `screens/panels/captures.py` — CapturesPanel for quick text captures, with "send to Vikunja" on double-press.
- `storage/repository.py` — Device SQLite has a `tasks` table (id TEXT, title, completed, due_date, created_at, updated_at) and `quick_captures` table. Methods: `add_task`, `list_incomplete_tasks`, `list_overdue_tasks`, `cache_today_tasks`.

**Notification infrastructure (`server/notifications/`):**
- `models.py` — NotificationEvent with Priority enum (1-5), category system (includes "task" and "reminder" categories).
- `dispatcher.py` — Dedup + fan-out to registered callbacks.
- `ws_handler.py` — DeviceWSHandler broadcasts to connected devices, supports reconnect replay.

### Gaps

1. **No Things 3 integration** — Vikunja adapter is the backend, but the user uses Things 3 on Mac. Tasks are invisible there.
2. **No subtasks, priority, reminder time, notes** — Device task table is bare minimum (title, completed, due_date).
3. **No update_task tool** — Agent can create and complete but cannot modify existing tasks.
4. **Task completion on device doesn't sync back** — TasksPanel marks `done` in local list but never calls the server.
5. **No reminder scheduling** — Heartbeat does 4-hour overdue checks, but no per-task "remind me at 3pm" capability.
6. **No living document pattern** — No reference implementation found in the codebase. This would be the agent editing/maintaining a persistent document (like a weekly plan) over time.

---

## Design Decisions

### 1. Data model: BITOS-owned SQLite with Things sync

**Decision: BITOS owns the task store in server SQLite. Things 3 is a sync target, not the source of truth.**

Rationale:
- Things 3 has no API — it only accepts input via URL scheme (`things:///add?title=...`) or the Things MCP server (which reads the SQLite database at `~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/Things Database.thingssql/main.sqlite`).
- The device needs offline-capable task access (Pi Zero disconnects from WiFi).
- The agent needs rich metadata (priority, reminder_at, subtasks, notes) that Things may not surface through MCP.
- Three-surface visibility (device, companion app, laptop) requires a canonical store that all surfaces can query.

Sync strategy:
- **BITOS -> Things**: On create/update, push to Things via URL scheme (`open -g "things:///add?..."` on Mac mini). For completion, use `things:///update?id=...&completed=true`.
- **Things -> BITOS**: Periodic poll (every 5 min) via Things MCP `get_today` / `get_inbox` tools, reconcile into BITOS task store. New tasks from Things get imported with a `source=things` flag.
- **Conflict resolution**: Last-write-wins with `updated_at` timestamp. Things completion always wins (user explicitly checked it off).

### 2. SQLite schema for enriched tasks

```sql
-- Server: server/data/tasks.db

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,                    -- uuid, e.g. "tsk_a1b2c3d4"
    title TEXT NOT NULL,
    notes TEXT DEFAULT '',                  -- rich notes / description
    priority INTEGER NOT NULL DEFAULT 3,    -- 1=critical, 2=high, 3=normal, 4=low
    status TEXT NOT NULL DEFAULT 'todo',    -- todo | in_progress | waiting | done | cancelled
    due_date TEXT,                          -- ISO date: "2026-03-18"
    due_time TEXT,                          -- ISO time: "14:00" (optional, for day-specific deadlines)
    reminder_at TEXT,                       -- ISO datetime: "2026-03-18T13:45:00" (when to fire reminder)
    reminder_fired INTEGER DEFAULT 0,       -- 1 if reminder already delivered
    recurrence TEXT,                        -- null | "daily" | "weekly" | "monthly" | cron-like
    project TEXT DEFAULT 'INBOX',           -- project/area grouping
    tags TEXT DEFAULT '[]',                 -- JSON array of tag strings
    parent_id TEXT,                         -- null for top-level, task id for subtasks
    sort_order INTEGER DEFAULT 0,           -- ordering within parent/project
    source TEXT DEFAULT 'agent',            -- agent | device | things | companion
    things_id TEXT,                         -- Things 3 UUID for sync (null if not synced)
    created_at TEXT NOT NULL,               -- ISO datetime
    updated_at TEXT NOT NULL,               -- ISO datetime
    completed_at TEXT,                      -- ISO datetime when marked done

    FOREIGN KEY (parent_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(status, due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_reminder ON tasks(reminder_at, reminder_fired) WHERE reminder_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_id) WHERE parent_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project, status);
CREATE INDEX IF NOT EXISTS idx_tasks_things ON tasks(things_id) WHERE things_id IS NOT NULL;
```

### 3. Agent tools

Replace the three Vikunja-proxied tools with a comprehensive set:

| Tool | Parameters | Description |
|------|-----------|-------------|
| `create_task` | title, notes?, due_date?, due_time?, reminder_at?, priority?, project?, tags?, parent_id? | Create task. Returns task with id. |
| `update_task` | task_id, title?, notes?, due_date?, due_time?, reminder_at?, priority?, status?, project?, tags? | Update any field(s) on an existing task. |
| `complete_task` | task_id | Mark task done, set completed_at. Fires completion to Things sync. |
| `delete_task` | task_id | Soft-delete (status=cancelled) or hard delete. |
| `add_subtask` | parent_id, title, notes?, due_date?, priority? | Convenience wrapper: creates task with parent_id set. |
| `get_tasks` | filter (today/all/overdue/project/search), project?, query?, status?, limit? | List tasks with flexible filtering. |
| `get_task` | task_id | Get single task with its subtasks. |
| `set_reminder` | task_id, remind_at | Set or update reminder time for a task. |
| `update_living_doc` | content | Write/update the user's weekly living document (see section 6). |

Tool definition example for `create_task`:

```python
{
    "name": "create_task",
    "description": (
        "Create a new task. The task will appear on the device, companion app, "
        "and sync to Things 3 on the laptop. Set a reminder_at to get a "
        "notification at a specific time. Priority: 1=critical, 2=high, "
        "3=normal (default), 4=low."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "title": {"type": "string", "description": "What needs to be done."},
            "notes": {"type": "string", "description": "Additional context or details."},
            "due_date": {"type": "string", "description": "Due date: YYYY-MM-DD."},
            "due_time": {"type": "string", "description": "Due time: HH:MM (24h)."},
            "reminder_at": {
                "type": "string",
                "description": "When to send a reminder: ISO datetime YYYY-MM-DDTHH:MM:SS.",
            },
            "priority": {
                "type": "integer", "enum": [1, 2, 3, 4],
                "description": "1=critical, 2=high, 3=normal, 4=low.",
            },
            "project": {"type": "string", "description": "Project name (default INBOX)."},
            "tags": {
                "type": "array", "items": {"type": "string"},
                "description": "Tags for categorization.",
            },
            "parent_id": {
                "type": "string",
                "description": "Parent task ID to create this as a subtask.",
            },
        },
        "required": ["title"],
    },
}
```

### 4. Reminder architecture

**How reminders trigger: Heartbeat-driven, not separate timer.**

The existing heartbeat loop ticks every 60 seconds. Add a new check in `_tick()`:

```
async def _check_task_reminders(self, now: datetime) -> None:
    """Fire any task reminders whose reminder_at <= now and not yet fired."""
    db = _get_task_db()
    due_reminders = db.execute(
        "SELECT * FROM tasks WHERE reminder_at IS NOT NULL "
        "AND reminder_fired = 0 AND reminder_at <= ? AND status = 'todo'",
        (now.isoformat(),)
    ).fetchall()

    for task in due_reminders:
        # Build notification
        event = NotificationEvent(
            type="task_reminder",
            priority=Priority.HIGH,  # or map from task.priority
            category="reminder",
            payload={
                "task_id": task["id"],
                "title": task["title"],
                "due_date": task["due_date"],
                "notes": (task["notes"] or "")[:100],
            }
        )
        # Dispatch through notification system
        dispatcher.dispatch(event)

        # Also broadcast via /ws/proactive for immediate device display
        await _broadcast_to_devices({
            "type": "task_reminder",
            "task_id": task["id"],
            "title": task["title"],
            "message": f"Reminder: {task['title']}",
            "timestamp": now.isoformat(),
        })

        # Mark fired
        db.execute(
            "UPDATE tasks SET reminder_fired = 1, updated_at = ? WHERE id = ?",
            (now.isoformat(), task["id"])
        )
    db.commit()
```

**Delivery path:**
1. Heartbeat tick detects `reminder_at <= now`
2. Creates `NotificationEvent` (category="reminder", priority=HIGH)
3. Dispatches through `NotificationDispatcher` (dedup, persist, fan-out)
4. `DeviceWSHandler` broadcasts to connected devices via WebSocket
5. Device shows notification toast/banner (existing notification overlay system)
6. Also broadcasts via `/ws/proactive` for the proactive message overlay

**Recurring reminders:** If `recurrence` is set, after firing, compute next `reminder_at` based on recurrence pattern and update the task.

### 5. Sync strategy: BITOS <-> Things 3

```
                    ┌──────────────┐
                    │  BITOS Tasks │  (server/data/tasks.db)
                    │   SQLite     │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
         ┌────▼────┐  ┌───▼────┐  ┌───▼────┐
         │ Device  │  │Compan. │  │Things 3│
         │ Pi Zero │  │  PWA   │  │  Mac   │
         └─────────┘  └────────┘  └────────┘
```

**New file: `server/integrations/things_adapter.py`**

Things 3 on Mac exposes data two ways:
1. **Read**: Direct SQLite read from `~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/Things Database.thingssql/main.sqlite` (read-only, Things uses WAL mode).
2. **Write**: URL scheme `things:///add`, `things:///update`, via `open -g` subprocess.

```python
class ThingsAdapter:
    """Read from Things SQLite, write via URL scheme."""

    THINGS_DB = os.path.expanduser(
        "~/Library/Group Containers/"
        "JLMPQHK86H.com.culturedcode.ThingsMac/"
        "Things Database.thingssql/main.sqlite"
    )

    def read_today(self) -> list[dict]:
        """Read today's tasks from Things database."""
        ...

    def read_inbox(self) -> list[dict]:
        """Read inbox tasks."""
        ...

    def push_task(self, title, notes=None, when=None, tags=None, list_name=None) -> str:
        """Create task in Things via URL scheme. Returns Things ID."""
        params = urllib.parse.urlencode({
            "title": title,
            "notes": notes or "",
            "when": when or "",  # "today", "tomorrow", ISO date
            "tags": ",".join(tags or []),
            "list": list_name or "",
            "reveal": "false",
        })
        subprocess.run(["open", "-g", f"things:///add?{params}"], check=True)
        ...

    def complete_task(self, things_id: str) -> bool:
        """Complete a task in Things."""
        subprocess.run(
            ["open", "-g", f"things:///update?id={things_id}&completed=true"],
            check=True,
        )
        return True
```

**Sync loop (new scheduled_action in heartbeat):**

```python
# New heartbeat action: "things_sync"
# Runs every 5 minutes during active hours

async def _handle_things_sync() -> str | None:
    """Bidirectional sync between BITOS tasks DB and Things 3."""
    adapter = ThingsAdapter()
    task_db = _get_task_db()

    # 1. Import new tasks from Things that aren't in BITOS yet
    things_tasks = adapter.read_today() + adapter.read_inbox()
    for tt in things_tasks:
        existing = task_db.execute(
            "SELECT id FROM tasks WHERE things_id = ?", (tt["uuid"],)
        ).fetchone()
        if not existing:
            # Import with source='things'
            _insert_task(task_db, title=tt["title"], things_id=tt["uuid"], source="things", ...)

    # 2. Push BITOS tasks that don't have a things_id yet
    unsynced = task_db.execute(
        "SELECT * FROM tasks WHERE things_id IS NULL AND source != 'things' AND status = 'todo'"
    ).fetchall()
    for task in unsynced:
        things_id = adapter.push_task(task["title"], notes=task["notes"], ...)
        task_db.execute(
            "UPDATE tasks SET things_id = ?, updated_at = ? WHERE id = ?",
            (things_id, now_iso, task["id"])
        )

    # 3. Sync completions
    # Check Things for tasks we track that are now complete
    for task in task_db.execute("SELECT * FROM tasks WHERE things_id IS NOT NULL AND status = 'todo'"):
        things_task = adapter.get_task(task["things_id"])
        if things_task and things_task.get("completed"):
            _complete_task(task_db, task["id"])

    task_db.commit()
    return None  # Silent sync, no proactive message
```

### 6. Living document pattern

The "living document" is a persistent markdown document the agent maintains, similar to a weekly planning sheet. The agent can read and edit it as a tool call, the same way it would edit any task.

**Implementation:**

Store as a special task record with `project = '__LIVING_DOC__'` or as a separate table:

```sql
CREATE TABLE IF NOT EXISTS living_documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,               -- "Weekly Plan" / "Daily Log"
    content TEXT NOT NULL DEFAULT '',   -- Markdown content
    doc_type TEXT NOT NULL DEFAULT 'weekly',  -- weekly | daily | custom
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

Agent tool: `update_living_doc` — reads current content, the agent edits it (add items, check off completed, add notes), and writes back. The heartbeat could prompt the agent to update the living doc during morning briefing.

On device: a new panel or a view within the markdown viewer (`screens/panels/markdown_viewer.py`) that renders the living doc.

---

## Implementation Plan

### Phase 1: Task store + agent tools (server only)

**Files to create/modify:**

| File | Action | Description |
|------|--------|-------------|
| `server/task_store.py` | **CREATE** | SQLite task store with full CRUD, migration, query methods |
| `server/agent_tools.py` | **MODIFY** | Replace 3 Vikunja task tools with 9 new tools, update handler |
| `server/main.py` | **MODIFY** | Replace `GET /tasks/today` with richer endpoints: `GET /tasks`, `GET /tasks/{id}`, `POST /tasks`, `PUT /tasks/{id}`, `DELETE /tasks/{id}` |
| `server/heartbeat.py` | **MODIFY** | Add `_check_task_reminders()` to tick loop, add `things_sync` action |

Estimated effort: 1 session

### Phase 2: Things 3 adapter + sync

**Files to create/modify:**

| File | Action | Description |
|------|--------|-------------|
| `server/integrations/things_adapter.py` | **CREATE** | Read Things SQLite, write via URL scheme |
| `server/heartbeat.py` | **MODIFY** | Add `things_sync` scheduled action (5-min poll) |
| `server/task_store.py` | **MODIFY** | Add sync reconciliation methods |

Estimated effort: 1 session

### Phase 3: Device UI overhaul

**Files to create/modify:**

| File | Action | Description |
|------|--------|-------------|
| `device/screens/panels/tasks.py` | **MODIFY** | Show priority indicators, due dates, subtask counts; add detail view on double-press; sync completion back to server |
| `device/storage/repository.py` | **MODIFY** | Upgrade tasks table schema to match server (migration 7), add sync methods |
| `device/client/api.py` | **MODIFY** | Add `complete_task(id)`, `get_task(id)`, new task endpoints |

Estimated effort: 1 session

### Phase 4: Reminder delivery + living doc

**Files to create/modify:**

| File | Action | Description |
|------|--------|-------------|
| `server/heartbeat.py` | **MODIFY** | Wire reminder firing through notification dispatcher |
| `server/task_store.py` | **MODIFY** | Add living_documents table and CRUD |
| `server/agent_tools.py` | **MODIFY** | Add `update_living_doc` tool |
| `device/screens/panels/tasks.py` | **MODIFY** | Handle incoming reminder notifications (highlight task) |

Estimated effort: 1 session

### Phase 5: Retire Vikunja

**Files to modify:**

| File | Action | Description |
|------|--------|-------------|
| `server/integrations/vikunja_adapter.py` | **DEPRECATE** | Keep for reference, remove from active code paths |
| `server/agent_tools.py` | **MODIFY** | Remove Vikunja singleton |
| `server/main.py` | **MODIFY** | Remove Vikunja health checks |
| `device/screens/panels/captures.py` | **MODIFY** | Send captures to BITOS task store instead of Vikunja |

Estimated effort: 0.5 session

---

## API Endpoints (final state)

```
GET    /tasks                  — List tasks (query params: status, project, due_before, due_after, parent_id, q)
GET    /tasks/{task_id}        — Get task with subtasks
POST   /tasks                  — Create task
PUT    /tasks/{task_id}        — Update task
DELETE /tasks/{task_id}        — Delete/cancel task
POST   /tasks/{task_id}/complete — Mark complete
GET    /tasks/today            — Shortcut: today's tasks (backward compat)
GET    /tasks/overdue          — Shortcut: overdue tasks

GET    /living-doc             — Get current living document
PUT    /living-doc             — Update living document content

GET    /things/sync            — Trigger immediate Things sync (debug)
GET    /things/status          — Things sync status
```

---

## Key architectural notes

1. **Task IDs are UUIDs** (`tsk_` prefix), not integers. This avoids collision between device-created and server-created tasks.

2. **Device caches tasks locally** for offline display. Server is the source of truth. Device polls `GET /tasks/today` and caches in local SQLite. Task completions on device are queued via the existing `outbound_commands` table and retried.

3. **Reminders are heartbeat-driven**, not a separate daemon. The 60-second tick is precise enough for reminder delivery (worst case 59 seconds late, acceptable for a companion device).

4. **Things sync is one-way-dominant**: BITOS is the canonical store. Things is a mirror for laptop visibility. If a task is edited in Things directly, the next sync picks it up, but BITOS metadata (priority, subtasks, reminder_at) may not have Things equivalents.

5. **The notification system already supports task reminders.** `models.py` has `category="reminder"` with `Priority.CRITICAL` and `category="task"` with `Priority.HIGH`. No new notification infrastructure needed.

6. **Vikunja gets retired**, not ripped out immediately. The adapter stays as a fallback during migration. Once Things sync is proven, Vikunja references are removed.
