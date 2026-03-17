"""Tests for server/task_store.py — CRUD, queries, filters, subtasks, living docs."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "server" / "integrations"))


class TaskStoreTests(unittest.TestCase):
    def setUp(self):
        import task_store
        self._tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmpfile.close()
        task_store.set_db_path(self._tmpfile.name)

    def tearDown(self):
        import task_store
        task_store.close_db()
        os.unlink(self._tmpfile.name)

    def test_create_task_returns_dict_with_id(self):
        import task_store
        task = task_store.create_task(title="Buy groceries")
        self.assertTrue(task["id"].startswith("tsk_"))
        self.assertEqual(task["title"], "Buy groceries")
        self.assertEqual(task["status"], "todo")
        self.assertEqual(task["priority"], 3)
        self.assertEqual(task["project"], "INBOX")

    def test_create_task_with_all_fields(self):
        import task_store
        task = task_store.create_task(
            title="Ship feature",
            notes="Deploy to prod",
            priority=1,
            due_date="2026-03-20",
            due_time="14:00",
            reminder_at="2026-03-20T13:45:00",
            project="BITOS",
            tags=["urgent", "dev"],
            source="device",
        )
        self.assertEqual(task["priority"], 1)
        self.assertEqual(task["due_date"], "2026-03-20")
        self.assertEqual(task["due_time"], "14:00")
        self.assertEqual(task["reminder_at"], "2026-03-20T13:45:00")
        self.assertEqual(task["project"], "BITOS")
        self.assertEqual(task["tags"], ["urgent", "dev"])
        self.assertEqual(task["source"], "device")

    def test_get_task_not_found(self):
        import task_store
        self.assertIsNone(task_store.get_task("tsk_nonexistent"))

    def test_update_task(self):
        import task_store
        task = task_store.create_task(title="Original")
        updated = task_store.update_task(task["id"], title="Updated", priority=2)
        self.assertEqual(updated["title"], "Updated")
        self.assertEqual(updated["priority"], 2)

    def test_update_task_not_found(self):
        import task_store
        self.assertIsNone(task_store.update_task("tsk_fake", title="x"))

    def test_complete_task(self):
        import task_store
        task = task_store.create_task(title="Finish report")
        completed = task_store.complete_task(task["id"])
        self.assertEqual(completed["status"], "done")
        self.assertIsNotNone(completed["completed_at"])

    def test_delete_task_soft(self):
        import task_store
        task = task_store.create_task(title="Delete me")
        ok = task_store.delete_task(task["id"])
        self.assertTrue(ok)
        deleted = task_store.get_task(task["id"])
        self.assertEqual(deleted["status"], "cancelled")

    def test_delete_task_hard(self):
        import task_store
        task = task_store.create_task(title="Delete hard")
        ok = task_store.delete_task(task["id"], hard=True)
        self.assertTrue(ok)
        self.assertIsNone(task_store.get_task(task["id"]))

    def test_delete_task_not_found(self):
        import task_store
        self.assertFalse(task_store.delete_task("tsk_fake"))

    def test_add_subtask(self):
        import task_store
        parent = task_store.create_task(title="Parent", project="WORK")
        sub = task_store.add_subtask(parent["id"], title="Child")
        self.assertEqual(sub["parent_id"], parent["id"])
        self.assertEqual(sub["project"], "WORK")

        # Get parent should include subtask
        parent_full = task_store.get_task(parent["id"])
        self.assertEqual(len(parent_full["subtasks"]), 1)
        self.assertEqual(parent_full["subtasks"][0]["title"], "Child")

    def test_add_subtask_parent_not_found(self):
        import task_store
        with self.assertRaises(ValueError):
            task_store.add_subtask("tsk_fake", title="Orphan")

    def test_set_reminder(self):
        import task_store
        task = task_store.create_task(title="Remind me")
        updated = task_store.set_reminder(task["id"], "2026-03-20T10:00:00")
        self.assertEqual(updated["reminder_at"], "2026-03-20T10:00:00")
        self.assertEqual(updated["reminder_fired"], 0)

    def test_list_tasks_today(self):
        import task_store
        task_store.create_task(title="Today task", due_date="2020-01-01")
        task_store.create_task(title="No due date")
        tasks = task_store.get_today_tasks()
        titles = [t["title"] for t in tasks]
        self.assertIn("Today task", titles)
        self.assertIn("No due date", titles)

    def test_list_tasks_overdue(self):
        import task_store
        task_store.create_task(title="Overdue", due_date="2020-01-01")
        task_store.create_task(title="Future", due_date="2099-01-01")
        overdue = task_store.get_overdue_tasks()
        titles = [t["title"] for t in overdue]
        self.assertIn("Overdue", titles)
        self.assertNotIn("Future", titles)

    def test_list_tasks_by_project(self):
        import task_store
        task_store.create_task(title="Work thing", project="WORK")
        task_store.create_task(title="Personal", project="PERSONAL")
        tasks = task_store.list_tasks(project="WORK")
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["title"], "Work thing")

    def test_list_tasks_search(self):
        import task_store
        task_store.create_task(title="Buy milk")
        task_store.create_task(title="Write code")
        tasks = task_store.list_tasks(query="milk")
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["title"], "Buy milk")

    def test_list_tasks_excludes_cancelled(self):
        import task_store
        task = task_store.create_task(title="Cancelled")
        task_store.delete_task(task["id"])  # soft delete = cancelled
        tasks = task_store.list_tasks()
        titles = [t["title"] for t in tasks]
        self.assertNotIn("Cancelled", titles)

    def test_list_tasks_top_level_only_by_default(self):
        import task_store
        parent = task_store.create_task(title="Parent")
        task_store.add_subtask(parent["id"], title="Sub")
        tasks = task_store.list_tasks()
        titles = [t["title"] for t in tasks]
        self.assertIn("Parent", titles)
        self.assertNotIn("Sub", titles)

    def test_get_due_reminders(self):
        import task_store
        task = task_store.create_task(title="Remind", reminder_at="2020-01-01T10:00:00")
        reminders = task_store.get_due_reminders("2026-01-01T00:00:00")
        self.assertEqual(len(reminders), 1)
        self.assertEqual(reminders[0]["id"], task["id"])

    def test_mark_reminder_fired(self):
        import task_store
        task = task_store.create_task(title="Fire me", reminder_at="2020-01-01T10:00:00")
        task_store.mark_reminder_fired(task["id"])
        reminders = task_store.get_due_reminders("2026-01-01T00:00:00")
        self.assertEqual(len(reminders), 0)

    def test_advance_recurring_reminder(self):
        import task_store
        task = task_store.create_task(title="Daily", reminder_at="2026-03-17T08:00:00")
        task_store.update_task(task["id"], recurrence="daily")
        task_store.mark_reminder_fired(task["id"])
        task_store.advance_recurring_reminder(task["id"])
        updated = task_store.get_task(task["id"])
        self.assertEqual(updated["reminder_fired"], 0)
        self.assertIn("2026-03-18", updated["reminder_at"])

    def test_living_doc_create_and_update(self):
        import task_store
        doc = task_store.update_living_doc("# Week 12\n- Plan stuff")
        self.assertTrue(doc["id"].startswith("doc_"))
        self.assertEqual(doc["content"], "# Week 12\n- Plan stuff")

        # Update existing
        doc2 = task_store.update_living_doc("# Week 12\n- Plan stuff\n- Done")
        self.assertEqual(doc2["id"], doc["id"])
        self.assertIn("Done", doc2["content"])

    def test_get_living_doc(self):
        import task_store
        self.assertIsNone(task_store.get_living_doc())
        task_store.update_living_doc("content here")
        doc = task_store.get_living_doc()
        self.assertIsNotNone(doc)
        self.assertEqual(doc["content"], "content here")

    def test_find_by_things_id(self):
        import task_store
        task = task_store.create_task(title="Synced", things_id="THINGS-UUID-123")
        found = task_store.find_by_things_id("THINGS-UUID-123")
        self.assertIsNotNone(found)
        self.assertEqual(found["id"], task["id"])

    def test_get_unsynced_tasks(self):
        import task_store
        task_store.create_task(title="Unsynced", source="agent")
        task_store.create_task(title="Already synced", source="agent", things_id="X")
        task_store.create_task(title="From Things", source="things")
        unsynced = task_store.get_unsynced_tasks()
        titles = [t["title"] for t in unsynced]
        self.assertIn("Unsynced", titles)
        self.assertNotIn("Already synced", titles)
        self.assertNotIn("From Things", titles)


class TaskStoreAgentToolTests(unittest.TestCase):
    """Test the agent tool handlers use the task store correctly."""

    def setUp(self):
        import task_store
        self._tmpfile = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmpfile.close()
        task_store.set_db_path(self._tmpfile.name)
        self._ds = {}
        self._sc = []

    def tearDown(self):
        import task_store
        task_store.close_db()
        os.unlink(self._tmpfile.name)

    def _call(self, name, inp):
        from agent_tools import handle_tool_call
        return json.loads(handle_tool_call(name, inp, self._ds, self._sc))

    def test_agent_create_task(self):
        result = self._call("create_task", {"title": "Agent task"})
        self.assertTrue(result["success"])
        self.assertTrue(result["task"]["id"].startswith("tsk_"))

    def test_agent_get_tasks(self):
        self._call("create_task", {"title": "Visible"})
        result = self._call("get_tasks", {"filter": "today"})
        self.assertGreaterEqual(result["count"], 1)

    def test_agent_complete_task(self):
        created = self._call("create_task", {"title": "To complete"})
        task_id = created["task"]["id"]
        result = self._call("complete_task", {"task_id": task_id})
        self.assertTrue(result["success"])

    def test_agent_delete_task(self):
        created = self._call("create_task", {"title": "To delete"})
        task_id = created["task"]["id"]
        result = self._call("delete_task", {"task_id": task_id})
        self.assertTrue(result["success"])

    def test_agent_add_subtask(self):
        parent = self._call("create_task", {"title": "Parent"})
        parent_id = parent["task"]["id"]
        result = self._call("add_subtask", {"parent_id": parent_id, "title": "Sub"})
        self.assertTrue(result["success"])
        self.assertEqual(result["task"]["parent_id"], parent_id)

    def test_agent_get_task(self):
        created = self._call("create_task", {"title": "Detail"})
        task_id = created["task"]["id"]
        result = self._call("get_task", {"task_id": task_id})
        self.assertTrue(result["success"])
        self.assertEqual(result["task"]["title"], "Detail")

    def test_agent_set_reminder(self):
        created = self._call("create_task", {"title": "Remind"})
        task_id = created["task"]["id"]
        result = self._call("set_reminder", {"task_id": task_id, "remind_at": "2026-03-20T10:00:00"})
        self.assertTrue(result["success"])
        self.assertEqual(result["task"]["reminder_at"], "2026-03-20T10:00:00")

    def test_agent_update_task(self):
        created = self._call("create_task", {"title": "Original"})
        task_id = created["task"]["id"]
        result = self._call("update_task", {"task_id": task_id, "title": "Renamed", "priority": 1})
        self.assertTrue(result["success"])
        self.assertEqual(result["task"]["title"], "Renamed")
        self.assertEqual(result["task"]["priority"], 1)

    def test_agent_update_living_doc(self):
        result = self._call("update_living_doc", {"content": "# Plan\n- Task 1"})
        self.assertTrue(result["success"])
        self.assertIn("Plan", result["document"]["content"])


if __name__ == "__main__":
    unittest.main()
