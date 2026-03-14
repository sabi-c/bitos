"""SQLite-backed local persistence for device sessions/messages/settings/events."""
from __future__ import annotations

import os
import sqlite3
import time
from contextlib import closing


DEFAULT_DB_PATH = "device/data/bitos.db"
LATEST_SCHEMA_VERSION = 2


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
