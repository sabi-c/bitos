import tempfile
import unittest
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from notifications.poller import NotificationPoller
from overlays.notification import NotificationQueue
from storage.repository import DeviceRepository


class _ApiStub:
    def __init__(self, states):
        self._states = list(states)

    def health(self):
        if not self._states:
            return False
        return self._states.pop(0)


class NotificationPollerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = DeviceRepository(db_path=str(Path(self.tmp.name) / "bitos.db"))
        self.repo.initialize()

    def tearDown(self):
        self.tmp.cleanup()

    def _records(self, queue):
        return queue.get_all()

    def test_health_change_online_to_offline_fires_notification(self):
        queue = NotificationQueue(repository=self.repo)
        poller = NotificationPoller(queue=queue, api_client=_ApiStub([True, False]), repository=self.repo)
        poller._poll_health_state()
        poller._poll_health_state()
        records = self._records(queue)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].message, "AI went offline")

    def test_health_change_offline_to_online_fires_notification(self):
        queue = NotificationQueue(repository=self.repo)
        poller = NotificationPoller(queue=queue, api_client=_ApiStub([False, True]), repository=self.repo)
        poller._poll_health_state()
        poller._poll_health_state()
        records = self._records(queue)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].message, "AI back online")

    def test_no_duplicate_fires_when_state_repeats(self):
        queue = NotificationQueue(repository=self.repo)
        poller = NotificationPoller(queue=queue, api_client=_ApiStub([True, True, True]), repository=self.repo)
        poller._poll_health_state()
        poller._poll_health_state()
        poller._poll_health_state()
        self.assertEqual(len(self._records(queue)), 0)

    def test_overdue_task_fires_once_not_repeat(self):
        queue = NotificationQueue(repository=self.repo)
        self.repo.add_task(task_id="t-1", title="Ship patch", due_date="2024-01-01", completed=False)
        poller = NotificationPoller(queue=queue, api_client=_ApiStub([True]), repository=self.repo)
        poller._poll_overdue_tasks()
        poller._poll_overdue_tasks()
        records = self._records(queue)
        self.assertEqual(len(records), 1)
        self.assertIn("overdue", records[0].message)

    def test_no_notification_without_state_change(self):
        queue = NotificationQueue(repository=self.repo)
        poller = NotificationPoller(queue=queue, api_client=_ApiStub([False]), repository=self.repo)
        poller._poll_health_state()
        self.assertEqual(len(self._records(queue)), 0)


if __name__ == "__main__":
    unittest.main()
