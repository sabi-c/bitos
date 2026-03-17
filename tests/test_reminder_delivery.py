"""Tests for reminder delivery through the notification system + REST endpoints."""
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
# Ensure server is first so notifications package is found
if str(ROOT / "server") in sys.path:
    sys.path.remove(str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "server" / "integrations"))

from fastapi.testclient import TestClient


class ReminderDeliveryTests(unittest.TestCase):
    """Test reminder firing through the full heartbeat + notification path."""

    def setUp(self):
        import task_store
        self._tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmpfile.close()
        task_store.set_db_path(self._tmpfile.name)

    def tearDown(self):
        import task_store
        task_store.close_db()
        os.unlink(self._tmpfile.name)

    def test_reminder_creates_notification_event(self):
        """Reminder firing should mark the task as fired and broadcast."""
        import asyncio
        import task_store

        task = task_store.create_task(
            title="Call dentist",
            reminder_at="2020-01-01T09:00:00",
            priority=2,
        )

        from heartbeat import _HeartbeatEngine
        engine = _HeartbeatEngine()
        now = datetime(2026, 3, 17, 12, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
        asyncio.get_event_loop().run_until_complete(engine._check_task_reminders(now))

        # Task should be marked fired
        updated = task_store.get_task(task["id"])
        self.assertEqual(updated["reminder_fired"], 1)

    def test_reminder_broadcast_payload(self):
        """Verify the /ws/proactive broadcast payload structure."""
        import asyncio
        import task_store
        from unittest.mock import AsyncMock, patch

        task = task_store.create_task(
            title="Meeting prep",
            reminder_at="2020-01-01T09:00:00",
        )

        broadcast_payloads = []

        async def mock_broadcast(payload):
            broadcast_payloads.append(payload)

        with patch("heartbeat._broadcast_to_devices", side_effect=mock_broadcast):
            from heartbeat import _HeartbeatEngine
            engine = _HeartbeatEngine()
            now = datetime(2026, 3, 17, 12, 0, 0, tzinfo=ZoneInfo("America/Los_Angeles"))
            asyncio.get_event_loop().run_until_complete(engine._check_task_reminders(now))

        self.assertEqual(len(broadcast_payloads), 1)
        payload = broadcast_payloads[0]
        self.assertEqual(payload["type"], "task_reminder")
        self.assertEqual(payload["task_id"], task["id"])
        self.assertEqual(payload["title"], "Meeting prep")
        self.assertIn("Reminder:", payload["message"])


class TaskRESTEndpointTests(unittest.TestCase):
    """Test the new task REST endpoints in main.py."""

    def setUp(self):
        import task_store
        self._tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmpfile.close()
        task_store.set_db_path(self._tmpfile.name)
        import main as server_main
        self.client = TestClient(server_main.app)

    def tearDown(self):
        import task_store
        task_store.close_db()
        os.unlink(self._tmpfile.name)

    def test_create_task_endpoint(self):
        resp = self.client.post("/tasks", json={"title": "Test task", "priority": 2})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data["id"].startswith("tsk_"))
        self.assertEqual(data["title"], "Test task")
        self.assertEqual(data["priority"], 2)

    def test_get_task_endpoint(self):
        created = self.client.post("/tasks", json={"title": "Get me"}).json()
        resp = self.client.get(f"/tasks/{created['id']}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["title"], "Get me")

    def test_get_task_not_found(self):
        resp = self.client.get("/tasks/tsk_nonexist")
        self.assertEqual(resp.status_code, 404)

    def test_update_task_endpoint(self):
        created = self.client.post("/tasks", json={"title": "Original"}).json()
        resp = self.client.put(f"/tasks/{created['id']}", json={"title": "Updated"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["title"], "Updated")

    def test_delete_task_endpoint(self):
        created = self.client.post("/tasks", json={"title": "Delete me"}).json()
        resp = self.client.delete(f"/tasks/{created['id']}")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()["ok"])

    def test_complete_task_endpoint(self):
        created = self.client.post("/tasks", json={"title": "Complete me"}).json()
        resp = self.client.post(f"/tasks/{created['id']}/complete")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["status"], "done")
        self.assertIsNotNone(resp.json()["completed_at"])

    def test_list_tasks_endpoint(self):
        self.client.post("/tasks", json={"title": "Task A"})
        self.client.post("/tasks", json={"title": "Task B"})
        resp = self.client.get("/tasks")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json()["count"], 2)

    def test_tasks_today_endpoint(self):
        self.client.post("/tasks", json={"title": "Today task"})
        resp = self.client.get("/tasks/today")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("tasks", resp.json())

    def test_tasks_overdue_endpoint(self):
        self.client.post("/tasks", json={"title": "Old task", "due_date": "2020-01-01"})
        resp = self.client.get("/tasks/overdue")
        self.assertEqual(resp.status_code, 200)
        self.assertGreaterEqual(resp.json()["count"], 1)

    def test_living_doc_roundtrip(self):
        # Initially empty
        resp = self.client.get("/living-doc")
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()["document"])

        # Create
        resp = self.client.put("/living-doc", json={"content": "# Week Plan\n- Task 1"})
        self.assertEqual(resp.status_code, 200)
        doc = resp.json()["document"]
        self.assertIn("Week Plan", doc["content"])

        # Read back
        resp = self.client.get("/living-doc")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["document"]["content"], "# Week Plan\n- Task 1")


if __name__ == "__main__":
    unittest.main()
