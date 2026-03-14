"""SQLite-backed local persistence for device sessions/messages/settings/events."""
from __future__ import annotations

import os
import sqlite3
import time
from contextlib import closing


DEFAULT_DB_PATH = "device/data/bitos.db"
LATEST_SCHEMA_VERSION = 1


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
