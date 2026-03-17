"""SQLite-backed task store for BITOS.

Rich task management with priority, subtasks, reminders, projects, and tags.
Uses WAL mode, same pattern as conversation_store.py.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).resolve().parent / "data" / "tasks.db"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
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
    """)


# Initialise tables on import
_init_conn = _get_conn()
_ensure_tables(_init_conn)
_init_conn.close()


def _new_id() -> str:
    return f"tsk_{uuid.uuid4().hex[:12]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    # Parse tags JSON
    if "tags" in d and isinstance(d["tags"], str):
        try:
            d["tags"] = json.loads(d["tags"])
        except (json.JSONDecodeError, TypeError):
            d["tags"] = []
    return d


# ── CRUD ─────────────────────────────────────────────────────────────────


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
    """Create a new task. Returns the created task dict."""
    task_id = _new_id()
    now = _now_iso()
    tags_json = json.dumps(tags or [])

    conn = _get_conn()
    try:
        conn.execute(
            """INSERT INTO tasks
               (id, title, notes, priority, status, due_date, due_time,
                reminder_at, reminder_fired, recurrence, project, tags,
                parent_id, sort_order, source, things_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'todo', ?, ?, ?, 0, ?, ?, ?, ?, 0, ?, ?, ?, ?)""",
            (
                task_id, title, notes, priority, due_date, due_time,
                reminder_at, recurrence, project, tags_json,
                parent_id, source, things_id, now, now,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_task(task_id: str) -> dict | None:
    """Get a single task by ID, including subtasks."""
    conn = _get_conn()
    try:
        row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if not row:
            return None
        task = _row_to_dict(row)
        # Attach subtasks
        subtask_rows = conn.execute(
            "SELECT * FROM tasks WHERE parent_id = ? ORDER BY sort_order, created_at",
            (task_id,),
        ).fetchall()
        task["subtasks"] = [_row_to_dict(r) for r in subtask_rows]
        return task
    finally:
        conn.close()


def update_task(task_id: str, **fields: Any) -> dict | None:
    """Update fields on an existing task. Returns updated task or None if not found."""
    allowed = {
        "title", "notes", "priority", "status", "due_date", "due_time",
        "reminder_at", "reminder_fired", "recurrence", "project", "tags",
        "parent_id", "sort_order", "source", "things_id", "completed_at",
    }
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return get_task(task_id)

    # Serialize tags to JSON if present
    if "tags" in updates and isinstance(updates["tags"], list):
        updates["tags"] = json.dumps(updates["tags"])

    updates["updated_at"] = _now_iso()

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [task_id]

    conn = _get_conn()
    try:
        cursor = conn.execute(
            f"UPDATE tasks SET {set_clause} WHERE id = ?",
            values,
        )
        if cursor.rowcount == 0:
            return None
        conn.commit()
        return get_task(task_id)
    finally:
        conn.close()


def complete_task(task_id: str) -> dict | None:
    """Mark a task as done with completed_at timestamp."""
    now = _now_iso()
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "UPDATE tasks SET status = 'done', completed_at = ?, updated_at = ? WHERE id = ?",
            (now, now, task_id),
        )
        if cursor.rowcount == 0:
            return None
        conn.commit()
        return get_task(task_id)
    finally:
        conn.close()


def delete_task(task_id: str, hard: bool = False) -> bool:
    """Delete a task. Soft-delete (cancel) by default, hard delete if specified."""
    conn = _get_conn()
    try:
        if hard:
            cursor = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        else:
            now = _now_iso()
            cursor = conn.execute(
                "UPDATE tasks SET status = 'cancelled', updated_at = ? WHERE id = ?",
                (now, task_id),
            )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def list_tasks(
    status: str | None = None,
    priority: int | None = None,
    project: str | None = None,
    due_before: str | None = None,
    due_after: str | None = None,
    search: str | None = None,
    parent_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """List tasks with flexible filters."""
    conditions: list[str] = []
    params: list[Any] = []

    if status:
        conditions.append("status = ?")
        params.append(status)
    else:
        # By default exclude cancelled
        conditions.append("status != 'cancelled'")

    if priority is not None:
        conditions.append("priority = ?")
        params.append(priority)

    if project:
        conditions.append("project = ?")
        params.append(project)

    if due_before:
        conditions.append("due_date IS NOT NULL AND due_date <= ?")
        params.append(due_before)

    if due_after:
        conditions.append("due_date IS NOT NULL AND due_date >= ?")
        params.append(due_after)

    if search:
        conditions.append("(title LIKE ? OR notes LIKE ?)")
        pattern = f"%{search}%"
        params.extend([pattern, pattern])

    if parent_id is not None:
        conditions.append("parent_id = ?")
        params.append(parent_id)
    else:
        # By default only top-level tasks
        conditions.append("parent_id IS NULL")

    where = " AND ".join(conditions) if conditions else "1=1"
    params.append(limit)

    conn = _get_conn()
    try:
        rows = conn.execute(
            f"""SELECT * FROM tasks
                WHERE {where}
                ORDER BY priority ASC, due_date ASC NULLS LAST, created_at DESC
                LIMIT ?""",
            params,
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_subtasks(parent_id: str) -> list[dict]:
    """Get all subtasks for a parent task."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE parent_id = ? ORDER BY sort_order, created_at",
            (parent_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_today_tasks() -> list[dict]:
    """Get tasks due today or overdue, excluding done/cancelled."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT * FROM tasks
               WHERE status IN ('todo', 'in_progress', 'waiting')
                 AND parent_id IS NULL
                 AND (due_date IS NOT NULL AND due_date <= ?)
               ORDER BY priority ASC, due_date ASC
               LIMIT 50""",
            (today,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_due_reminders(now_iso: str) -> list[dict]:
    """Get tasks with unfired reminders that are due."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT * FROM tasks
               WHERE reminder_at IS NOT NULL
                 AND reminder_fired = 0
                 AND reminder_at <= ?
                 AND status IN ('todo', 'in_progress', 'waiting')""",
            (now_iso,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def mark_reminder_fired(task_id: str) -> None:
    """Mark a task's reminder as fired."""
    now = _now_iso()
    conn = _get_conn()
    try:
        conn.execute(
            "UPDATE tasks SET reminder_fired = 1, updated_at = ? WHERE id = ?",
            (now, task_id),
        )
        conn.commit()
    finally:
        conn.close()


def list_projects() -> list[str]:
    """Return distinct project names from active tasks."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT DISTINCT project FROM tasks
               WHERE status != 'cancelled'
               ORDER BY project""",
        ).fetchall()
        return [r["project"] for r in rows]
    finally:
        conn.close()
