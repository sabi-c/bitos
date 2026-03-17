"""BITOS Task Store — SQLite-backed task management with full CRUD.

Owns the canonical task store. Things 3 is a sync target, not source of truth.
Task IDs use 'tsk_' prefix + 8 hex chars from uuid4.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DATA_DIR / "tasks.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    notes TEXT DEFAULT '',
    priority INTEGER NOT NULL DEFAULT 3,
    status TEXT NOT NULL DEFAULT 'todo',
    due_date TEXT,
    due_time TEXT,
    reminder_at TEXT,
    reminder_fired INTEGER DEFAULT 0,
    recurrence TEXT,
    project TEXT DEFAULT 'INBOX',
    tags TEXT DEFAULT '[]',
    parent_id TEXT,
    sort_order INTEGER DEFAULT 0,
    source TEXT DEFAULT 'agent',
    things_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,

    FOREIGN KEY (parent_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(status, due_date);
CREATE INDEX IF NOT EXISTS idx_tasks_reminder ON tasks(reminder_at, reminder_fired)
    WHERE reminder_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_parent ON tasks(parent_id)
    WHERE parent_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project, status);
CREATE INDEX IF NOT EXISTS idx_tasks_things ON tasks(things_id)
    WHERE things_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS living_documents (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    content TEXT NOT NULL DEFAULT '',
    doc_type TEXT NOT NULL DEFAULT 'weekly',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _generate_id() -> str:
    return f"tsk_{uuid.uuid4().hex[:8]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _get_db(db_path: str | Path | None = None) -> sqlite3.Connection:
    """Open task store database, creating schema if needed."""
    path = Path(db_path) if db_path else DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=3000")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


# ── Module-level DB singleton ────────────────────────────────────────────

_db: sqlite3.Connection | None = None
_db_path_override: str | Path | None = None


def set_db_path(path: str | Path | None) -> None:
    """Override the database path (for testing). Call before any operations."""
    global _db, _db_path_override
    if _db is not None:
        try:
            _db.close()
        except Exception:
            pass
        _db = None
    _db_path_override = path


def get_db() -> sqlite3.Connection:
    global _db
    if _db is None:
        _db = _get_db(_db_path_override)
    return _db


def close_db() -> None:
    global _db
    if _db is not None:
        _db.close()
        _db = None


# ── Task CRUD ────────────────────────────────────────────────────────────

def create_task(
    title: str,
    notes: str = "",
    priority: int = 3,
    due_date: str | None = None,
    due_time: str | None = None,
    reminder_at: str | None = None,
    recurrence: str | None = None,
    project: str = "INBOX",
    tags: list[str] | None = None,
    parent_id: str | None = None,
    source: str = "agent",
    things_id: str | None = None,
) -> dict:
    """Create a new task. Returns the full task dict."""
    db = get_db()
    task_id = _generate_id()
    now = _now_iso()
    tags_json = json.dumps(tags or [])

    db.execute(
        """INSERT INTO tasks
           (id, title, notes, priority, status, due_date, due_time,
            reminder_at, reminder_fired, recurrence, project, tags,
            parent_id, sort_order, source, things_id, created_at, updated_at)
           VALUES (?, ?, ?, ?, 'todo', ?, ?, ?, 0, ?, ?, ?, ?, 0, ?, ?, ?, ?)""",
        (task_id, title, notes, priority, due_date, due_time,
         reminder_at, recurrence, project, tags_json, parent_id, source, things_id, now, now),
    )
    db.commit()
    logger.info("task_created: id=%s title=%s", task_id, title[:40])
    return get_task(task_id)


def get_task(task_id: str) -> dict | None:
    """Get a single task by ID, including subtasks."""
    db = get_db()
    row = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not row:
        return None
    task = _row_to_dict(row)
    # Attach subtasks
    subtasks = db.execute(
        "SELECT * FROM tasks WHERE parent_id = ? AND status != 'cancelled' ORDER BY sort_order, created_at",
        (task_id,),
    ).fetchall()
    task["subtasks"] = [_row_to_dict(s) for s in subtasks]
    return task


def update_task(task_id: str, **fields) -> dict | None:
    """Update fields on an existing task. Returns updated task or None."""
    db = get_db()
    existing = db.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not existing:
        return None

    allowed = {
        "title", "notes", "priority", "status", "due_date", "due_time",
        "reminder_at", "reminder_fired", "recurrence", "project", "tags",
        "sort_order", "things_id", "completed_at",
    }
    updates = {}
    for key, val in fields.items():
        if key in allowed:
            if key == "tags" and isinstance(val, list):
                updates[key] = json.dumps(val)
            else:
                updates[key] = val

    if not updates:
        return get_task(task_id)

    updates["updated_at"] = _now_iso()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [task_id]
    db.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", values)
    db.commit()
    logger.info("task_updated: id=%s fields=%s", task_id, list(updates.keys()))
    return get_task(task_id)


def complete_task(task_id: str) -> dict | None:
    """Mark a task as done. Returns updated task or None."""
    now = _now_iso()
    return update_task(task_id, status="done", completed_at=now)


def delete_task(task_id: str, hard: bool = False) -> bool:
    """Delete a task. Soft-delete by default (status=cancelled)."""
    db = get_db()
    existing = db.execute("SELECT id FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not existing:
        return False
    if hard:
        db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    else:
        now = _now_iso()
        db.execute(
            "UPDATE tasks SET status = 'cancelled', updated_at = ? WHERE id = ?",
            (now, task_id),
        )
    db.commit()
    logger.info("task_deleted: id=%s hard=%s", task_id, hard)
    return True


def add_subtask(
    parent_id: str,
    title: str,
    notes: str = "",
    due_date: str | None = None,
    priority: int = 3,
    source: str = "agent",
) -> dict:
    """Convenience: create a task with parent_id set."""
    parent = get_task(parent_id)
    if not parent:
        raise ValueError(f"Parent task {parent_id} not found")
    return create_task(
        title=title,
        notes=notes,
        priority=priority,
        due_date=due_date,
        parent_id=parent_id,
        project=parent.get("project", "INBOX"),
        source=source,
    )


def set_reminder(task_id: str, remind_at: str) -> dict | None:
    """Set or update a reminder time on a task."""
    return update_task(task_id, reminder_at=remind_at, reminder_fired=0)


# ── Query Methods ────────────────────────────────────────────────────────

def list_tasks(
    status: str | None = None,
    project: str | None = None,
    parent_id: str | None = "TOP_LEVEL",
    due_before: str | None = None,
    due_after: str | None = None,
    query: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List tasks with flexible filtering.

    parent_id="TOP_LEVEL" (default) returns only top-level tasks.
    parent_id=None returns all tasks regardless of nesting.
    parent_id="<id>" returns children of that task.
    """
    db = get_db()
    conditions = []
    params: list[Any] = []

    if status:
        conditions.append("status = ?")
        params.append(status)
    else:
        conditions.append("status NOT IN ('cancelled')")

    if project:
        conditions.append("project = ?")
        params.append(project)

    if parent_id == "TOP_LEVEL":
        conditions.append("parent_id IS NULL")
    elif parent_id is not None:
        conditions.append("parent_id = ?")
        params.append(parent_id)

    if due_before:
        conditions.append("due_date IS NOT NULL AND due_date < ?")
        params.append(due_before)

    if due_after:
        conditions.append("due_date IS NOT NULL AND due_date >= ?")
        params.append(due_after)

    if query:
        conditions.append("(title LIKE ? OR notes LIKE ?)")
        like = f"%{query}%"
        params.extend([like, like])

    where = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)

    rows = db.execute(
        f"SELECT * FROM tasks WHERE {where} "
        "ORDER BY priority ASC, COALESCE(due_date, '9999-12-31') ASC, sort_order ASC, created_at ASC "
        f"LIMIT ?",
        params,
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_today_tasks() -> list[dict]:
    """Get tasks due today or with no due date that are active."""
    today = _today_iso()
    db = get_db()
    rows = db.execute(
        """SELECT * FROM tasks
           WHERE status IN ('todo', 'in_progress')
             AND parent_id IS NULL
             AND (due_date IS NULL OR due_date <= ?)
           ORDER BY priority ASC, COALESCE(due_date, '9999-12-31') ASC, sort_order ASC
           LIMIT 20""",
        (today,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_overdue_tasks() -> list[dict]:
    """Get tasks with due_date before today that are still open."""
    today = _today_iso()
    db = get_db()
    rows = db.execute(
        """SELECT * FROM tasks
           WHERE status IN ('todo', 'in_progress')
             AND due_date IS NOT NULL
             AND due_date < ?
             AND parent_id IS NULL
           ORDER BY due_date ASC, priority ASC""",
        (today,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_due_reminders(now_iso: str) -> list[dict]:
    """Get tasks with unfired reminders that are due."""
    db = get_db()
    rows = db.execute(
        """SELECT * FROM tasks
           WHERE reminder_at IS NOT NULL
             AND reminder_fired = 0
             AND reminder_at <= ?
             AND status IN ('todo', 'in_progress')""",
        (now_iso,),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def mark_reminder_fired(task_id: str) -> None:
    """Mark a task's reminder as fired."""
    db = get_db()
    now = _now_iso()
    db.execute(
        "UPDATE tasks SET reminder_fired = 1, updated_at = ? WHERE id = ?",
        (now, task_id),
    )
    db.commit()


def advance_recurring_reminder(task_id: str) -> None:
    """For recurring tasks, compute and set next reminder_at after firing."""
    db = get_db()
    row = db.execute(
        "SELECT recurrence, reminder_at FROM tasks WHERE id = ?", (task_id,),
    ).fetchone()
    if not row or not row["recurrence"] or not row["reminder_at"]:
        return

    recurrence = row["recurrence"]
    try:
        current = datetime.fromisoformat(row["reminder_at"])
    except (ValueError, TypeError):
        return

    from datetime import timedelta
    deltas = {
        "daily": timedelta(days=1),
        "weekly": timedelta(weeks=1),
        "monthly": timedelta(days=30),  # approximate
    }
    delta = deltas.get(recurrence)
    if not delta:
        return

    next_at = current + delta
    now = _now_iso()
    db.execute(
        "UPDATE tasks SET reminder_at = ?, reminder_fired = 0, updated_at = ? WHERE id = ?",
        (next_at.isoformat(), now, task_id),
    )
    db.commit()
    logger.info("recurring_reminder_advanced: id=%s next=%s", task_id, next_at.isoformat())


def list_projects() -> list[str]:
    """Return distinct project names from active tasks."""
    db = get_db()
    rows = db.execute(
        """SELECT DISTINCT project FROM tasks
           WHERE status NOT IN ('cancelled')
           ORDER BY project""",
    ).fetchall()
    return [r["project"] for r in rows]


# ── Living Documents ─────────────────────────────────────────────────────

def get_living_doc(doc_type: str = "weekly") -> dict | None:
    """Get the current living document of given type."""
    db = get_db()
    row = db.execute(
        "SELECT * FROM living_documents WHERE doc_type = ? ORDER BY updated_at DESC LIMIT 1",
        (doc_type,),
    ).fetchone()
    if not row:
        return None
    return dict(row)


def update_living_doc(content: str, title: str = "Weekly Plan", doc_type: str = "weekly") -> dict:
    """Create or update the living document."""
    db = get_db()
    now = _now_iso()
    existing = db.execute(
        "SELECT id FROM living_documents WHERE doc_type = ? ORDER BY updated_at DESC LIMIT 1",
        (doc_type,),
    ).fetchone()

    if existing:
        doc_id = existing["id"]
        db.execute(
            "UPDATE living_documents SET title = ?, content = ?, updated_at = ? WHERE id = ?",
            (title, content, now, doc_id),
        )
    else:
        doc_id = f"doc_{uuid.uuid4().hex[:8]}"
        db.execute(
            "INSERT INTO living_documents (id, title, content, doc_type, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (doc_id, title, content, doc_type, now, now),
        )
    db.commit()
    return dict(db.execute("SELECT * FROM living_documents WHERE id = ?", (doc_id,)).fetchone())


# ── Sync Helpers ─────────────────────────────────────────────────────────

def find_by_things_id(things_id: str) -> dict | None:
    """Find a BITOS task by its Things 3 UUID."""
    db = get_db()
    row = db.execute("SELECT * FROM tasks WHERE things_id = ?", (things_id,)).fetchone()
    return _row_to_dict(row) if row else None


def get_unsynced_tasks() -> list[dict]:
    """Get tasks that haven't been pushed to Things yet."""
    db = get_db()
    rows = db.execute(
        "SELECT * FROM tasks WHERE things_id IS NULL AND source != 'things' AND status = 'todo'",
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_tracked_open_tasks() -> list[dict]:
    """Get open tasks that have a things_id (for completion sync)."""
    db = get_db()
    rows = db.execute(
        "SELECT * FROM tasks WHERE things_id IS NOT NULL AND status IN ('todo', 'in_progress')",
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


# ── Helpers ──────────────────────────────────────────────────────────────

def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a Row to a plain dict with parsed tags."""
    d = dict(row)
    if "tags" in d and isinstance(d["tags"], str):
        try:
            d["tags"] = json.loads(d["tags"])
        except (json.JSONDecodeError, TypeError):
            d["tags"] = []
    return d
