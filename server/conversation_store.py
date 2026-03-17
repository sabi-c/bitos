"""SQLite-backed multi-turn conversation store for BITOS chat."""
from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "conversations.db"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_tables(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id)
        );
        CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
    """)


# Initialise tables on import
_init_conn = _get_conn()
_ensure_tables(_init_conn)
_init_conn.close()


def create_conversation() -> str:
    """Create a new conversation and return its ID."""
    conv_id = uuid.uuid4().hex[:12]
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO conversations (id, created_at, updated_at) VALUES (?, ?, ?)",
            (conv_id, now, now),
        )
        conn.commit()
        return conv_id
    finally:
        conn.close()


def add_message(conversation_id: str, role: str, content: str) -> None:
    """Append a message to a conversation."""
    now = datetime.now(timezone.utc).isoformat()
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            (conversation_id, role, content, now),
        )
        conn.execute(
            "UPDATE conversations SET updated_at = ? WHERE id = ?",
            (now, conversation_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_messages(conversation_id: str, limit: int = 20) -> list[dict]:
    """Return the last `limit` messages for a conversation, oldest first."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT role, content, created_at FROM messages
               WHERE conversation_id = ?
               ORDER BY id DESC LIMIT ?""",
            (conversation_id, limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]
    finally:
        conn.close()


def list_conversations(limit: int = 20) -> list[dict]:
    """Return recent conversations with message count and last message preview."""
    conn = _get_conn()
    try:
        rows = conn.execute(
            """SELECT c.id, c.created_at, c.updated_at,
                      COUNT(m.id) AS message_count
               FROM conversations c
               LEFT JOIN messages m ON m.conversation_id = c.id
               GROUP BY c.id
               ORDER BY c.updated_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

        results = []
        for row in rows:
            # Get last message preview
            last_msg = conn.execute(
                """SELECT content FROM messages
                   WHERE conversation_id = ?
                   ORDER BY id DESC LIMIT 1""",
                (row["id"],),
            ).fetchone()
            preview = ""
            if last_msg:
                preview = last_msg["content"][:100]

            results.append({
                "id": row["id"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "message_count": row["message_count"],
                "last_message_preview": preview,
            })
        return results
    finally:
        conn.close()


def get_conversation(conversation_id: str) -> dict | None:
    """Return full conversation with all messages."""
    conn = _get_conn()
    try:
        conv = conn.execute(
            "SELECT id, created_at, updated_at FROM conversations WHERE id = ?",
            (conversation_id,),
        ).fetchone()
        if not conv:
            return None

        messages = conn.execute(
            """SELECT role, content, created_at FROM messages
               WHERE conversation_id = ?
               ORDER BY id ASC""",
            (conversation_id,),
        ).fetchall()

        return {
            "id": conv["id"],
            "created_at": conv["created_at"],
            "updated_at": conv["updated_at"],
            "messages": [dict(m) for m in messages],
        }
    finally:
        conn.close()
