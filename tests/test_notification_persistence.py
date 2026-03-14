import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from overlays.notification import NotificationQueue, NotificationRecord
from storage.repository import DeviceRepository


class NotificationPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = DeviceRepository(db_path=str(Path(self.tmp.name) / "bitos.db"))
        self.repo.initialize()
        self.queue = NotificationQueue(repository=self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def test_push_record_persists_to_db(self):
        self.queue.push_record(
            NotificationRecord(
                id="notif-1",
                type="CLAUDE",
                app_name="CLAUDE",
                message="AI back online",
                time_str="10:00",
            )
        )
        rows = self.repo.list_notifications(limit=10)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "notif-1")

    def test_get_all_returns_from_db(self):
        self.queue.push_record(NotificationRecord(id="a", type="SMS", app_name="SMS", message="m1", time_str="10:01"))
        self.queue.push_record(NotificationRecord(id="b", type="MAIL", app_name="MAIL", message="m2", time_str="10:02"))
        records = self.queue.get_all()
        self.assertEqual(len(records), 2)
        self.assertEqual({records[0].id, records[1].id}, {"a", "b"})

    def test_mark_read_updates_db(self):
        self.queue.push_record(NotificationRecord(id="x", type="TASK", app_name="TASKS", message="Overdue", time_str="10:03"))
        self.queue.mark_read("x")
        rec = [r for r in self.queue.get_all() if r.id == "x"][0]
        self.assertTrue(rec.read)

    def test_overflow_trims_to_fifty_rows(self):
        for i in range(60):
            self.queue.push_record(
                NotificationRecord(
                    id=f"n-{i}",
                    type="CLAUDE",
                    app_name="CLAUDE",
                    message=str(i),
                    time_str="10:00",
                )
            )
        rows = self.repo.list_notifications(limit=100)
        self.assertEqual(len(rows), 50)


if __name__ == "__main__":
    unittest.main()
