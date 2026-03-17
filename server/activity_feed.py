"""Activity Feed — tracks all agent actions with visual status.

SQLite-backed activity log with pending → running → done/failed states.
Broadcasts updates via WebSocket to connected companion apps.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DATA_DIR / "activity.db"

# Activity types
ACTIVITY_TYPES = {
    "chat", "task_create", "task_complete", "message_sent", "email_sent",
    "setting_change", "approval", "quick_action", "message_read", "email_read",
    "calendar_read", "contact_search",
}

# Status flow: pending → running → done | failed
VALID_STATUSES = {"pending", "running", "done", "failed"}

# ── WebSocket subscribers ────────────────────────────────────────────────
_ws_clients: set = set()


def register_ws(ws) -> None:
    _ws_clients.add(ws)


def unregister_ws(ws) -> None:
    _ws_clients.discard(ws)


async def _broadcast(event: dict) -> None:
    """Best-effort broadcast to all connected activity WS clients."""
    dead = set()
    for ws in _ws_clients:
        try:
            await ws.send_json(event)
        except Exception:
            dead.add(ws)
    _ws_clients.difference_update(dead)


# ── Database setup ───────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=3000")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS activities (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            result TEXT,
            metadata TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_activities_type ON activities(type)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_activities_created ON activities(created_at DESC)
    """)
    conn.commit()
    return conn


def _row_to_dict(row: sqlite3.Row) -> dict:
    d = dict(row)
    if d.get("metadata"):
        try:
            d["metadata"] = json.loads(d["metadata"])
        except (json.JSONDecodeError, TypeError):
            pass
    return d


# ── Public API ───────────────────────────────────────────────────────────

def log_activity(
    activity_type: str,
    title: str,
    metadata: dict[str, Any] | None = None,
    status: str = "pending",
) -> str:
    """Create a new activity entry. Returns the activity ID."""
    activity_id = f"act_{uuid.uuid4().hex[:10]}"
    now = time.time()
    meta_json = json.dumps(metadata) if metadata else None

    db = _get_db()
    try:
        db.execute(
            "INSERT INTO activities (id, type, title, status, metadata, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (activity_id, activity_type, title, status, meta_json, now, now),
        )
        db.commit()
    finally:
        db.close()

    logger.info("activity_logged: id=%s type=%s title=%s", activity_id, activity_type, title[:50])
    return activity_id


def update_activity(
    activity_id: str,
    status: str,
    result: str | None = None,
) -> bool:
    """Update an activity's status and optional result. Returns True if found."""
    if status not in VALID_STATUSES:
        logger.warning("invalid_activity_status: %s", status)
        return False

    now = time.time()
    db = _get_db()
    try:
        cur = db.execute(
            "UPDATE activities SET status=?, result=?, updated_at=? WHERE id=?",
            (status, result, now, activity_id),
        )
        db.commit()
        return cur.rowcount > 0
    finally:
        db.close()


def get_recent(limit: int = 50) -> list[dict]:
    """Get recent activities, newest first."""
    limit = min(max(1, limit), 200)
    db = _get_db()
    try:
        rows = db.execute(
            "SELECT * FROM activities ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        db.close()


def get_by_type(activity_type: str, limit: int = 50) -> list[dict]:
    """Get activities filtered by type."""
    limit = min(max(1, limit), 200)
    db = _get_db()
    try:
        rows = db.execute(
            "SELECT * FROM activities WHERE type=? ORDER BY created_at DESC LIMIT ?",
            (activity_type, limit),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        db.close()


def get_by_id(activity_id: str) -> dict | None:
    """Get a single activity by ID."""
    db = _get_db()
    try:
        row = db.execute(
            "SELECT * FROM activities WHERE id=?",
            (activity_id,),
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        db.close()


# ── Convenience: log + run + update (wraps a tool call) ──────────────────

def track_tool_call(tool_name: str, tool_input: dict, execute_fn) -> str:
    """Log an activity, run the tool, update with result. Returns the tool result string."""
    type_map = {
        "create_task": "task_create",
        "complete_task": "task_complete",
        "get_tasks": "quick_action",
        "send_imessage": "message_sent",
        "read_imessages": "message_read",
        "send_email": "email_sent",
        "read_emails": "email_read",
        "get_calendar_events": "calendar_read",
        "get_contacts": "contact_search",
        "update_device_setting": "setting_change",
        "request_approval": "approval",
        "get_device_settings": "setting_change",
    }
    activity_type = type_map.get(tool_name, "chat")
    title = f"{tool_name}({json.dumps(tool_input)[:80]})"

    activity_id = log_activity(activity_type, title, metadata={"tool": tool_name, "input": tool_input})
    update_activity(activity_id, "running")

    try:
        result = execute_fn()
        # Determine success from result
        try:
            parsed = json.loads(result)
            failed = "error" in parsed
        except (json.JSONDecodeError, TypeError):
            failed = False

        status = "failed" if failed else "done"
        update_activity(activity_id, status, result=result[:500] if result else None)
        return result
    except Exception as exc:
        update_activity(activity_id, "failed", result=str(exc)[:500])
        raise
