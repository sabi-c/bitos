"""Tests for Things 3 adapter — read patterns, URL scheme generation, sync."""
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "server" / "integrations"))


def _create_things_db(db_path: str) -> None:
    """Create a minimal Things-like database for testing."""
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE TMArea (
            uuid TEXT PRIMARY KEY,
            title TEXT
        );
        CREATE TABLE TMTask (
            uuid TEXT PRIMARY KEY,
            title TEXT,
            notes TEXT DEFAULT '',
            status INTEGER DEFAULT 0,
            "start" INTEGER DEFAULT 0,
            type INTEGER DEFAULT 0,
            trashed INTEGER DEFAULT 0,
            project TEXT,
            area TEXT,
            actionGroup TEXT,
            startDate TEXT,
            dueDate TEXT,
            "index" INTEGER DEFAULT 0,
            FOREIGN KEY (project) REFERENCES TMTask(uuid),
            FOREIGN KEY (area) REFERENCES TMArea(uuid)
        );
        INSERT INTO TMArea (uuid, title) VALUES ('area1', 'Personal');
        -- Today task
        INSERT INTO TMTask (uuid, title, notes, status, start, type, trashed, project, area, "index")
        VALUES ('today1', 'Buy groceries', 'milk, eggs', 0, 1, 0, 0, NULL, 'area1', 0);
        -- Today task with project (type=1 means project in Things)
        INSERT INTO TMTask (uuid, title, notes, status, start, type, trashed, "index")
        VALUES ('proj1', 'BITOS Project', '', 0, 1, 1, 0, 0);
        INSERT INTO TMTask (uuid, title, status, start, type, trashed, project, "index")
        VALUES ('today2', 'Ship feature', 0, 1, 0, 0, 'proj1', 1);
        -- Inbox task
        INSERT INTO TMTask (uuid, title, status, start, type, trashed, "index")
        VALUES ('inbox1', 'Random idea', 0, 0, 0, 0, 0);
        -- Completed task (should not show in today)
        INSERT INTO TMTask (uuid, title, status, start, type, trashed, "index")
        VALUES ('done1', 'Done task', 3, 1, 0, 0, 2);
        -- Trashed task
        INSERT INTO TMTask (uuid, title, status, start, type, trashed, "index")
        VALUES ('trash1', 'Trashed', 0, 1, 0, 1, 3);
    """)
    conn.commit()
    conn.close()


class ThingsAdapterReadTests(unittest.TestCase):
    def setUp(self):
        self._tmpfile = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
        self._tmpfile.close()
        _create_things_db(self._tmpfile.name)
        from things_adapter import ThingsAdapter
        self.adapter = ThingsAdapter(db_path=self._tmpfile.name)

    def tearDown(self):
        os.unlink(self._tmpfile.name)

    def test_is_available(self):
        self.assertTrue(self.adapter.is_available)

    def test_read_today(self):
        tasks = self.adapter.read_today()
        titles = [t["title"] for t in tasks]
        self.assertIn("Buy groceries", titles)
        self.assertIn("Ship feature", titles)
        # Should not include completed, trashed, or inbox
        self.assertNotIn("Done task", titles)
        self.assertNotIn("Trashed", titles)
        self.assertNotIn("Random idea", titles)

    def test_read_today_task_fields(self):
        tasks = self.adapter.read_today()
        grocery = next(t for t in tasks if t["title"] == "Buy groceries")
        self.assertEqual(grocery["uuid"], "today1")
        self.assertEqual(grocery["notes"], "milk, eggs")
        self.assertFalse(grocery["completed"])

    def test_read_inbox(self):
        tasks = self.adapter.read_inbox()
        titles = [t["title"] for t in tasks]
        self.assertIn("Random idea", titles)
        self.assertNotIn("Buy groceries", titles)

    def test_read_task_by_uuid(self):
        task = self.adapter.read_task_by_uuid("today1")
        self.assertIsNotNone(task)
        self.assertEqual(task["title"], "Buy groceries")

    def test_read_task_by_uuid_not_found(self):
        task = self.adapter.read_task_by_uuid("nonexistent")
        self.assertIsNone(task)

    def test_not_available(self):
        from things_adapter import ThingsAdapter
        adapter = ThingsAdapter(db_path="/nonexistent/path.sqlite")
        self.assertFalse(adapter.is_available)
        self.assertEqual(adapter.read_today(), [])
        self.assertEqual(adapter.read_inbox(), [])


class ThingsAdapterWriteTests(unittest.TestCase):
    @patch("things_adapter.subprocess")
    def test_push_task_calls_open(self, mock_sp):
        from things_adapter import ThingsAdapter
        adapter = ThingsAdapter()
        adapter.push_task("Test task", notes="Details", when="today")
        mock_sp.run.assert_called_once()
        call_args = mock_sp.run.call_args
        url = call_args[0][0][2]  # ["open", "-g", url]
        self.assertIn("things:///add", url)
        self.assertIn("title=Test+task", url)
        self.assertIn("notes=Details", url)
        self.assertIn("when=today", url)

    @patch("things_adapter.subprocess")
    def test_complete_task_calls_open(self, mock_sp):
        from things_adapter import ThingsAdapter
        adapter = ThingsAdapter()
        adapter.complete_task("THINGS-UUID-123")
        mock_sp.run.assert_called_once()
        url = mock_sp.run.call_args[0][0][2]
        self.assertIn("things:///update", url)
        self.assertIn("id=THINGS-UUID-123", url)
        self.assertIn("completed=true", url)

    @patch("things_adapter.subprocess")
    def test_push_task_failure(self, mock_sp):
        mock_sp.run.side_effect = Exception("open failed")
        from things_adapter import ThingsAdapter
        adapter = ThingsAdapter()
        ok = adapter.push_task("Failing task")
        self.assertFalse(ok)


class ThingsSyncTests(unittest.TestCase):
    """Test the heartbeat sync handler with mocked adapters."""

    def setUp(self):
        import task_store
        self._tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmpfile.close()
        task_store.set_db_path(self._tmpfile.name)

    def tearDown(self):
        import task_store
        task_store.close_db()
        os.unlink(self._tmpfile.name)

    @patch("integrations.things_adapter.ThingsAdapter")
    def test_things_sync_imports_new_tasks(self, MockAdapter):
        """Sync should import tasks from Things that don't exist in BITOS."""
        import asyncio
        import task_store

        mock_instance = MagicMock()
        mock_instance.is_available = True
        mock_instance.read_today.return_value = [
            {"uuid": "things-1", "title": "From Things", "notes": "", "due_date": None, "project": "Work", "area": ""},
        ]
        mock_instance.read_inbox.return_value = []
        MockAdapter.return_value = mock_instance

        from heartbeat import _handle_things_sync
        asyncio.get_event_loop().run_until_complete(_handle_things_sync())

        found = task_store.find_by_things_id("things-1")
        self.assertIsNotNone(found)
        self.assertEqual(found["title"], "From Things")
        self.assertEqual(found["source"], "things")


class TaskReminderTests(unittest.TestCase):
    """Test the heartbeat reminder checker."""

    def setUp(self):
        import task_store
        self._tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmpfile.close()
        task_store.set_db_path(self._tmpfile.name)

    def tearDown(self):
        import task_store
        task_store.close_db()
        os.unlink(self._tmpfile.name)

    def test_reminder_fires_and_marks_fired(self):
        import asyncio
        import task_store
        from zoneinfo import ZoneInfo

        # Create a task with a past reminder
        task = task_store.create_task(title="Remind me", reminder_at="2020-01-01T10:00:00")
        self.assertEqual(task["reminder_fired"], 0)

        # Run the reminder check
        from heartbeat import _HeartbeatEngine
        engine = _HeartbeatEngine()
        now = datetime(2026, 3, 17, 12, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        asyncio.get_event_loop().run_until_complete(engine._check_task_reminders(now))

        # Task should be marked as fired
        updated = task_store.get_task(task["id"])
        self.assertEqual(updated["reminder_fired"], 1)

    def test_reminder_not_fired_if_future(self):
        import asyncio
        import task_store
        from zoneinfo import ZoneInfo

        task = task_store.create_task(title="Future", reminder_at="2099-01-01T10:00:00")

        from heartbeat import _HeartbeatEngine
        engine = _HeartbeatEngine()
        now = datetime(2026, 3, 17, 12, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        asyncio.get_event_loop().run_until_complete(engine._check_task_reminders(now))

        updated = task_store.get_task(task["id"])
        self.assertEqual(updated["reminder_fired"], 0)

    def test_recurring_reminder_advances(self):
        import asyncio
        import task_store
        from zoneinfo import ZoneInfo

        task = task_store.create_task(title="Daily", reminder_at="2026-03-17T08:00:00")
        task_store.update_task(task["id"], recurrence="daily")

        from heartbeat import _HeartbeatEngine
        engine = _HeartbeatEngine()
        now = datetime(2026, 3, 17, 12, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        asyncio.get_event_loop().run_until_complete(engine._check_task_reminders(now))

        updated = task_store.get_task(task["id"])
        # Should have advanced to next day and reset fired
        self.assertEqual(updated["reminder_fired"], 0)
        self.assertIn("2026-03-18", updated["reminder_at"])

    def test_dedup_no_double_fire(self):
        import asyncio
        import task_store
        from zoneinfo import ZoneInfo

        task = task_store.create_task(title="Once", reminder_at="2020-01-01T10:00:00")

        from heartbeat import _HeartbeatEngine
        engine = _HeartbeatEngine()
        now = datetime(2026, 3, 17, 12, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))

        # Fire once
        asyncio.get_event_loop().run_until_complete(engine._check_task_reminders(now))
        updated = task_store.get_task(task["id"])
        self.assertEqual(updated["reminder_fired"], 1)

        # Fire again — should not re-fire (already marked)
        asyncio.get_event_loop().run_until_complete(engine._check_task_reminders(now))
        still = task_store.get_task(task["id"])
        self.assertEqual(still["reminder_fired"], 1)


if __name__ == "__main__":
    unittest.main()
