"""Things 3 adapter — read from Things SQLite, write via URL scheme.

Things 3 on Mac exposes data two ways:
1. Read: Direct SQLite from ~/Library/Group Containers/JLMPQHK86H.com.culturedcode.ThingsMac/
2. Write: URL scheme things:///add, things:///update via `open -g` subprocess.
"""
from __future__ import annotations

import logging
import os
import sqlite3
import subprocess
import urllib.parse
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

THINGS_DB_PATH = os.path.expanduser(
    "~/Library/Group Containers/"
    "JLMPQHK86H.com.culturedcode.ThingsMac/"
    "Things Database.thingssql/main.sqlite"
)

# Things SQLite status mapping
# TMTask.status: 0=open, 1=cancelled, 2=open(in trash), 3=completed
# TMTask.start: 0=not started, 1=today, 2=someday
# TMTask.trashed: 0=not trashed, 1=trashed


class ThingsAdapter:
    """Read from Things 3 SQLite, write via URL scheme."""

    def __init__(self, db_path: str | None = None):
        self._db_path = db_path or THINGS_DB_PATH
        self._available: bool | None = None

    @property
    def is_available(self) -> bool:
        """Check if the Things database exists and is readable."""
        if self._available is None:
            self._available = Path(self._db_path).exists()
        return self._available

    def _connect(self) -> sqlite3.Connection:
        """Open read-only connection to Things database."""
        if not self.is_available:
            raise RuntimeError("Things 3 database not found")
        # Use immutable mode for read-only access (Things uses WAL)
        uri = f"file:{self._db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def read_today(self) -> list[dict]:
        """Read today's tasks from Things database."""
        if not self.is_available:
            return []
        try:
            conn = self._connect()
            rows = conn.execute("""
                SELECT
                    t.uuid,
                    t.title,
                    t.notes,
                    t.status,
                    t.startDate AS start_date,
                    t.dueDate AS due_date,
                    CASE WHEN t.status = 3 THEN 1 ELSE 0 END AS completed,
                    p.title AS project_title,
                    a.title AS area_title
                FROM TMTask t
                LEFT JOIN TMTask p ON t.project = p.uuid
                LEFT JOIN TMArea a ON t.area = a.uuid
                WHERE t.trashed = 0
                  AND t.status = 0
                  AND t.start = 1
                  AND t.type = 0
                ORDER BY t."index" ASC
            """).fetchall()
            conn.close()
            return [self._row_to_task(r) for r in rows]
        except Exception as exc:
            logger.warning("things_read_today_failed: %s", exc)
            return []

    def read_inbox(self) -> list[dict]:
        """Read inbox tasks from Things."""
        if not self.is_available:
            return []
        try:
            conn = self._connect()
            rows = conn.execute("""
                SELECT
                    t.uuid,
                    t.title,
                    t.notes,
                    t.status,
                    t.startDate AS start_date,
                    t.dueDate AS due_date,
                    CASE WHEN t.status = 3 THEN 1 ELSE 0 END AS completed,
                    NULL AS project_title,
                    NULL AS area_title
                FROM TMTask t
                WHERE t.trashed = 0
                  AND t.status = 0
                  AND t.start = 0
                  AND t.project IS NULL
                  AND t.actionGroup IS NULL
                  AND t.type = 0
                ORDER BY t."index" ASC
            """).fetchall()
            conn.close()
            return [self._row_to_task(r) for r in rows]
        except Exception as exc:
            logger.warning("things_read_inbox_failed: %s", exc)
            return []

    def read_task_by_uuid(self, things_uuid: str) -> dict | None:
        """Read a single task by its Things UUID."""
        if not self.is_available:
            return None
        try:
            conn = self._connect()
            row = conn.execute("""
                SELECT
                    t.uuid,
                    t.title,
                    t.notes,
                    t.status,
                    t.startDate AS start_date,
                    t.dueDate AS due_date,
                    CASE WHEN t.status = 3 THEN 1 ELSE 0 END AS completed,
                    p.title AS project_title,
                    a.title AS area_title
                FROM TMTask t
                LEFT JOIN TMTask p ON t.project = p.uuid
                LEFT JOIN TMArea a ON t.area = a.uuid
                WHERE t.uuid = ?
            """, (things_uuid,)).fetchone()
            conn.close()
            return self._row_to_task(row) if row else None
        except Exception as exc:
            logger.warning("things_read_task_failed: uuid=%s error=%s", things_uuid, exc)
            return None

    def push_task(
        self,
        title: str,
        notes: str | None = None,
        when: str | None = None,
        tags: list[str] | None = None,
        list_name: str | None = None,
        deadline: str | None = None,
    ) -> bool:
        """Create a task in Things via URL scheme. Returns success."""
        params: dict[str, str] = {"title": title, "reveal": "false"}
        if notes:
            params["notes"] = notes
        if when:
            params["when"] = when  # "today", "tomorrow", ISO date
        if tags:
            params["tags"] = ",".join(tags)
        if list_name:
            params["list"] = list_name
        if deadline:
            params["deadline"] = deadline

        url = f"things:///add?{urllib.parse.urlencode(params)}"
        try:
            subprocess.run(["open", "-g", url], check=True, timeout=5)
            logger.info("things_push_task: title=%s", title[:40])
            return True
        except Exception as exc:
            logger.warning("things_push_task_failed: %s", exc)
            return False

    def complete_task(self, things_uuid: str) -> bool:
        """Complete a task in Things via URL scheme."""
        url = f"things:///update?id={things_uuid}&completed=true"
        try:
            subprocess.run(["open", "-g", url], check=True, timeout=5)
            logger.info("things_complete_task: uuid=%s", things_uuid)
            return True
        except Exception as exc:
            logger.warning("things_complete_task_failed: %s", exc)
            return False

    @staticmethod
    def _row_to_task(row: sqlite3.Row) -> dict:
        """Convert a Things SQLite row to a task dict."""
        due = row["due_date"]
        # Things stores dates as floats (Cocoa timestamps) — seconds since 2001-01-01
        if due is not None and isinstance(due, (int, float)):
            from datetime import datetime, timedelta
            cocoa_epoch = datetime(2001, 1, 1)
            due = (cocoa_epoch + timedelta(seconds=due)).strftime("%Y-%m-%d")

        return {
            "uuid": row["uuid"],
            "title": row["title"] or "",
            "notes": row["notes"] or "",
            "completed": bool(row["completed"]),
            "due_date": due,
            "project": row["project_title"] or "",
            "area": row["area_title"] or "",
        }
