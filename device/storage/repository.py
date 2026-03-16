"""SQLite-backed local persistence for device sessions/messages/settings/events."""
from __future__ import annotations

import os
import sqlite3
import time
import uuid
import json
from contextlib import closing


DEFAULT_DB_PATH = "device/data/bitos.db"
LATEST_SCHEMA_VERSION = 6


MIGRATIONS: dict[int, str] = {
    1: """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        text TEXT NOT NULL,
        created_at REAL NOT NULL,
        FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at REAL NOT NULL
    );

    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        payload TEXT,
        created_at REAL NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_messages_session_created
      ON messages(session_id, created_at);
    """,
    2: """
    CREATE TABLE IF NOT EXISTS outbound_commands (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT NOT NULL,
        operation TEXT NOT NULL,
        payload TEXT NOT NULL,
        status TEXT NOT NULL,
        attempt_count INTEGER NOT NULL DEFAULT 0,
        max_attempts INTEGER NOT NULL DEFAULT 3,
        last_error TEXT,
        next_attempt_at REAL NOT NULL,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_outbound_commands_ready
      ON outbound_commands(status, next_attempt_at, created_at);
    """,
    3: """
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        completed INTEGER NOT NULL DEFAULT 0,
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_tasks_completed
      ON tasks(completed);
    """,
    4: """
    CREATE TABLE IF NOT EXISTS notifications (
        id TEXT PRIMARY KEY,
        type TEXT NOT NULL,
        app_name TEXT NOT NULL,
        message TEXT NOT NULL,
        time_str TEXT NOT NULL,
        read INTEGER NOT NULL DEFAULT 0,
        source_id TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_notifications_created
      ON notifications(created_at DESC);
    """,
    5: """
    CREATE TABLE IF NOT EXISTS quick_captures (
        id TEXT PRIMARY KEY,
        text TEXT NOT NULL,
        context TEXT DEFAULT '',
        sent_to_vikunja INTEGER DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE INDEX IF NOT EXISTS idx_quick_captures_created
      ON quick_captures(created_at DESC);
    """,
    6: """
    ALTER TABLE sessions ADD COLUMN session_type TEXT DEFAULT 'chat';
    CREATE INDEX IF NOT EXISTS idx_sessions_type_created
      ON sessions(session_type, created_at);
    """,
}


class DeviceRepository:
    """Convenience wrapper over local SQLite persistence."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.environ.get("BITOS_DB_FILE", DEFAULT_DB_PATH)

    def _connect(self) -> sqlite3.Connection:
        directory = os.path.dirname(self.db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def initialize(self) -> None:
        with closing(self._connect()) as conn:
            self._ensure_version_table(conn)
            current = self.get_schema_version(conn)
            for version in range(current + 1, LATEST_SCHEMA_VERSION + 1):
                conn.executescript(MIGRATIONS[version])
                if version >= 3:
                    self._ensure_tasks_due_date_column(conn)
                conn.execute("UPDATE schema_version SET version = ?", (version,))
            conn.commit()

    def _ensure_version_table(self, conn: sqlite3.Connection) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER NOT NULL
            )
            """
        )
        row = conn.execute("SELECT COUNT(*) AS c FROM schema_version").fetchone()
        if not row or row["c"] == 0:
            conn.execute("INSERT INTO schema_version(version) VALUES (0)")
        conn.commit()

    def _ensure_tasks_due_date_column(self, conn: sqlite3.Connection) -> None:
        task_table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='tasks'"
        ).fetchone()
        if not task_table:
            return
        cols = conn.execute("PRAGMA table_info(tasks)").fetchall()
        col_names = {str(row["name"]) for row in cols}
        if "due_date" not in col_names:
            conn.execute("ALTER TABLE tasks ADD COLUMN due_date TEXT")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_due_completed ON tasks(completed, due_date)")

    def get_schema_version(self, conn: sqlite3.Connection | None = None) -> int:
        if conn is None:
            with closing(self._connect()) as local_conn:
                return self.get_schema_version(local_conn)
        row = conn.execute("SELECT version FROM schema_version LIMIT 1").fetchone()
        return int(row["version"]) if row else 0

    def create_session(self, title: str | None = None) -> int:
        now = time.time()
        with closing(self._connect()) as conn:
            cur = conn.execute(
                "INSERT INTO sessions(title, created_at, updated_at) VALUES (?, ?, ?)",
                (title, now, now),
            )
            conn.commit()
            return int(cur.lastrowid)

    def get_latest_session_id(self) -> int | None:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT id FROM sessions ORDER BY updated_at DESC, id DESC LIMIT 1").fetchone()
            return int(row["id"]) if row else None

    def add_message(self, session_id: int, role: str, text: str) -> int:
        now = time.time()
        with closing(self._connect()) as conn:
            cur = conn.execute(
                "INSERT INTO messages(session_id, role, text, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, text, now),
            )
            conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
            conn.commit()
            return int(cur.lastrowid)

    def list_messages(self, session_id: int) -> list[dict]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT role, text, created_at FROM messages WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def load_latest_session_messages(self) -> tuple[int | None, list[dict]]:
        latest = self.get_latest_session_id()
        if latest is None:
            return None, []
        return latest, self.list_messages(latest)

    def get_setting(self, key: str, default=None):
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
            if not row:
                return default
            raw = str(row["value"])

        if isinstance(default, bool):
            return raw.strip().lower() in {"1", "true", "yes", "on"}
        if isinstance(default, int):
            try:
                return int(raw)
            except ValueError:
                return default
        if isinstance(default, float):
            try:
                return float(raw)
            except ValueError:
                return default
        return raw

    def set_setting(self, key: str, value) -> None:
        stored = value
        if isinstance(value, bool):
            stored = "true" if value else "false"
        elif not isinstance(value, str):
            stored = str(value)

        now = time.time()
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO settings(key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
                """,
                (key, str(stored), now),
            )
            conn.commit()

    def add_notification(self, record) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO notifications(id, type, app_name, message, time_str, read, source_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.type,
                    record.app_name,
                    record.message,
                    record.time_str,
                    1 if record.read else 0,
                    record.source_id,
                ),
            )
            conn.commit()

    def list_notifications(self, limit: int = 50) -> list[dict]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT id, type, app_name, message, time_str, read, source_id, created_at
                FROM notifications
                ORDER BY datetime(created_at) DESC, rowid DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def mark_notification_read(self, notification_id: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute("UPDATE notifications SET read = 1 WHERE id = ?", (notification_id,))
            conn.commit()

    def trim_notifications(self, max_rows: int = 50) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                DELETE FROM notifications
                WHERE id IN (
                    SELECT id FROM notifications
                    ORDER BY datetime(created_at) DESC, rowid DESC
                    LIMIT -1 OFFSET ?
                )
                """,
                (max_rows,),
            )
            conn.commit()

    def list_incomplete_tasks(self, limit: int = 3) -> list[dict]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT id, title, due_date, completed
                FROM tasks
                WHERE completed = 0
                ORDER BY COALESCE(date(due_date), date('9999-12-31')) ASC, datetime(updated_at) DESC, id ASC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def add_task(self, task_id: str, title: str, due_date: str | None = None, completed: bool = False) -> None:
        now = time.time()
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tasks(id, title, completed, due_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, COALESCE((SELECT created_at FROM tasks WHERE id = ?), ?), ?)
                """,
                (task_id, title, 1 if completed else 0, due_date, task_id, now, now),
            )
            conn.commit()

    def list_overdue_tasks(self, now_iso: str) -> list[dict]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT id, title, due_date, completed
                FROM tasks
                WHERE due_date IS NOT NULL
                  AND date(due_date) < date(?)
                  AND completed = 0
                ORDER BY date(due_date) ASC, id ASC
                """,
                (now_iso,),
            ).fetchall()
            return [dict(row) for row in rows]

    def save_quick_capture(self, text: str, context: str = "") -> str:
        """Saves capture, returns id."""
        capture_id = str(uuid.uuid4())[:8]
        with closing(self._connect()) as conn:
            conn.execute(
                """
                INSERT INTO quick_captures
                (id, text, context, created_at)
                VALUES (?, ?, ?, datetime('now'))
                """,
                (capture_id, text, context or ""),
            )
            conn.commit()
        return capture_id

    def get_recent_captures(self, limit: int = 10) -> list[dict]:
        """Returns most recent captures newest first."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT id, text, context, sent_to_vikunja, created_at
                FROM quick_captures
                ORDER BY datetime(created_at) DESC, rowid DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def get_capture_count(self) -> int:
        with closing(self._connect()) as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM quick_captures").fetchone()
            return int(row["c"]) if row else 0

    def mark_capture_sent_to_vikunja(self, capture_id: str) -> None:
        with closing(self._connect()) as conn:
            conn.execute("UPDATE quick_captures SET sent_to_vikunja = 1 WHERE id = ?", (capture_id,))
            conn.commit()

    def cache_today_tasks(self, tasks: list[dict]) -> None:
        self.set_setting("tasks_today_cache", json.dumps(tasks))

    def get_cached_today_tasks(self) -> list[dict]:
        raw = self.get_setting("tasks_today_cache", "")
        if not raw:
            return []
        try:
            payload = json.loads(raw)
            return payload if isinstance(payload, list) else []
        except Exception:
            return []

    def get_latest_session(self) -> dict | None:
        """Returns most recent session with messages."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT s.id, s.created_at,
                       COUNT(m.id) as msg_count
                FROM sessions s
                LEFT JOIN messages m ON m.session_id = s.id
                GROUP BY s.id
                HAVING msg_count > 0
                ORDER BY s.created_at DESC
                LIMIT 1
                """
            ).fetchone()
            if not row:
                return None
            return {"id": row[0], "created_at": row[1], "msg_count": row[2]}

    def create_greeting_session(self, greeting_text: str) -> int:
        """Create a greeting session with the agent's greeting as first message."""
        now = time.time()
        with closing(self._connect()) as conn:
            cur = conn.execute(
                "INSERT INTO sessions(title, session_type, created_at, updated_at) VALUES (?, 'greeting', ?, ?)",
                ("greeting", now, now),
            )
            session_id = int(cur.lastrowid)
            conn.execute(
                "INSERT INTO messages(session_id, role, text, created_at) VALUES (?, 'assistant', ?, ?)",
                (session_id, greeting_text, now),
            )
            conn.commit()
            return session_id

    def get_greeting_session(self) -> dict | None:
        """Get the most recent greeting session if less than 1 hour old."""
        cutoff = time.time() - 3600
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT s.id, s.created_at, s.updated_at
                FROM sessions s
                WHERE s.session_type = 'greeting'
                  AND s.created_at > ?
                ORDER BY s.created_at DESC
                LIMIT 1
                """,
                (cutoff,),
            ).fetchone()
            if not row:
                return None
            return {"id": int(row[0]), "created_at": row[1], "updated_at": row[2]}

    def get_latest_chat_session(self) -> dict | None:
        """Get the most recent non-greeting session with messages."""
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT s.id, s.title, s.created_at, s.updated_at,
                       COUNT(m.id) as msg_count
                FROM sessions s
                LEFT JOIN messages m ON m.session_id = s.id
                WHERE COALESCE(s.session_type, 'chat') = 'chat'
                GROUP BY s.id
                HAVING msg_count > 0
                ORDER BY s.updated_at DESC
                LIMIT 1
                """
            ).fetchone()
            if not row:
                return None
            return {
                "id": int(row[0]),
                "title": row[1],
                "created_at": row[2],
                "updated_at": row[3],
                "msg_count": int(row[4]),
            }

    def get_session_messages(self, session_id: str, limit: int = 10) -> list[dict]:
        """Returns last N messages for a session."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT role, text, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
            return [dict(row) for row in reversed(rows)]

    def queue_enqueue_command(self, domain: str, operation: str, payload: str, max_attempts: int = 3) -> int:
        now = time.time()
        with closing(self._connect()) as conn:
            cur = conn.execute(
                """
                INSERT INTO outbound_commands(
                    domain, operation, payload, status, attempt_count, max_attempts,
                    last_error, next_attempt_at, created_at, updated_at
                ) VALUES (?, ?, ?, 'pending', 0, ?, NULL, ?, ?, ?)
                """,
                (domain, operation, payload, max_attempts, now, now, now),
            )
            conn.commit()
            return int(cur.lastrowid)

    def queue_reserve_next_ready(self, now: float) -> dict | None:
        with closing(self._connect()) as conn:
            row = conn.execute(
                """
                SELECT *
                FROM outbound_commands
                WHERE status IN ('pending', 'retrying')
                  AND next_attempt_at <= ?
                ORDER BY next_attempt_at ASC, created_at ASC, id ASC
                LIMIT 1
                """,
                (now,),
            ).fetchone()
            if not row:
                return None
            command_id = int(row["id"])
            conn.execute(
                "UPDATE outbound_commands SET status = 'processing', updated_at = ? WHERE id = ?",
                (time.time(), command_id),
            )
            updated = conn.execute(
                "SELECT * FROM outbound_commands WHERE id = ?",
                (command_id,),
            ).fetchone()
            conn.commit()
            return dict(updated) if updated else None

    def queue_mark_succeeded(self, command_id: int) -> None:
        with closing(self._connect()) as conn:
            conn.execute(
                """
                UPDATE outbound_commands
                SET status = 'succeeded', last_error = NULL, updated_at = ?
                WHERE id = ?
                """,
                (time.time(), command_id),
            )
            conn.commit()

    def queue_mark_failed(
        self,
        command_id: int,
        reason: str,
        retryable: bool,
        backoff_seconds: float,
    ) -> str:
        now = time.time()
        with closing(self._connect()) as conn:
            row = conn.execute(
                "SELECT attempt_count, max_attempts FROM outbound_commands WHERE id = ?",
                (command_id,),
            ).fetchone()
            if not row:
                raise ValueError(f"Unknown command id {command_id}")
            attempts = int(row["attempt_count"]) + 1
            max_attempts = int(row["max_attempts"])
            if retryable and attempts < max_attempts:
                status = "retrying"
                next_attempt_at = now + max(0.0, backoff_seconds)
            else:
                status = "dead_letter"
                next_attempt_at = now
            conn.execute(
                """
                UPDATE outbound_commands
                SET status = ?, attempt_count = ?, last_error = ?, next_attempt_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, attempts, reason, next_attempt_at, now, command_id),
            )
            conn.commit()
            return status

    def queue_list_dead_letters(self, limit: int = 25) -> list[dict]:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM outbound_commands
                WHERE status = 'dead_letter'
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def queue_metrics(self) -> dict:
        with closing(self._connect()) as conn:
            rows = conn.execute(
                """
                SELECT status, COUNT(*) AS c
                FROM outbound_commands
                GROUP BY status
                """
            ).fetchall()
            counts = {row["status"]: int(row["c"]) for row in rows}
            retry_sum = conn.execute(
                "SELECT COALESCE(SUM(attempt_count), 0) AS total_retries FROM outbound_commands"
            ).fetchone()
            return {
                "pending": counts.get("pending", 0),
                "retrying": counts.get("retrying", 0),
                "processing": counts.get("processing", 0),
                "succeeded": counts.get("succeeded", 0),
                "dead_letter": counts.get("dead_letter", 0),
                "total_retries": int(retry_sum["total_retries"] if retry_sum else 0),
                "queue_depth": counts.get("pending", 0) + counts.get("retrying", 0) + counts.get("processing", 0),
            }
