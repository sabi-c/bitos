"""SQLite-backed persistent notification event queue."""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Optional

from .models import NotificationEvent, Priority

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notification_queue (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    priority    INTEGER NOT NULL,
    category    TEXT NOT NULL,
    payload     TEXT NOT NULL,
    timestamp   REAL NOT NULL,
    delivered   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_nq_delivered ON notification_queue(delivered);
CREATE INDEX IF NOT EXISTS idx_nq_timestamp ON notification_queue(timestamp);
"""


class QueueStore:
    """Persistent notification queue backed by SQLite."""

    def __init__(self, db_path: str | Path = ":memory:"):
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)

    # ------------------------------------------------------------------
    def push(self, event: NotificationEvent) -> None:
        """Insert an event into the queue."""
        import json
        self._conn.execute(
            "INSERT OR REPLACE INTO notification_queue "
            "(id, type, priority, category, payload, timestamp) VALUES (?,?,?,?,?,?)",
            (event.id, event.type, int(event.priority), event.category,
             json.dumps(event.payload), event.timestamp),
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    def get_pending(self) -> list[NotificationEvent]:
        """Return all events not yet marked delivered, ordered by priority then timestamp."""
        import json
        rows = self._conn.execute(
            "SELECT * FROM notification_queue WHERE delivered=0 "
            "ORDER BY priority ASC, timestamp ASC"
        ).fetchall()
        return [self._row_to_event(r) for r in rows]

    # ------------------------------------------------------------------
    def mark_delivered(self, event_id: str) -> None:
        """Mark an event as delivered."""
        self._conn.execute(
            "UPDATE notification_queue SET delivered=1 WHERE id=?", (event_id,)
        )
        self._conn.commit()

    # ------------------------------------------------------------------
    def get_since(self, since_ts: float) -> list[NotificationEvent]:
        """Replay events newer than *since_ts*, regardless of delivered status."""
        import json
        rows = self._conn.execute(
            "SELECT * FROM notification_queue WHERE timestamp > ? "
            "ORDER BY priority ASC, timestamp ASC",
            (since_ts,),
        ).fetchall()
        return [self._row_to_event(r) for r in rows]

    # ------------------------------------------------------------------
    def expire_older_than_hours(self, hours: float) -> int:
        """Delete delivered events older than *hours*. Returns count deleted."""
        cutoff = time.time() - hours * 3600
        cur = self._conn.execute(
            "DELETE FROM notification_queue WHERE delivered=1 AND timestamp < ?",
            (cutoff,),
        )
        self._conn.commit()
        return cur.rowcount

    # ------------------------------------------------------------------
    def close(self) -> None:
        self._conn.close()

    # ------------------------------------------------------------------
    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> NotificationEvent:
        import json
        return NotificationEvent(
            type=row["type"],
            priority=Priority(row["priority"]),
            category=row["category"],
            payload=json.loads(row["payload"]),
            id=row["id"],
            timestamp=row["timestamp"],
        )
