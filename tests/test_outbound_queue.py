import tempfile
import time
import unittest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from integrations.queue import OutboundCommandQueue
from storage.repository import DeviceRepository


class OutboundQueueTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = DeviceRepository(db_path=str(Path(self.tmp.name) / "bitos.db"))
        self.repo.initialize()
        self.queue = OutboundCommandQueue(self.repo)

    def tearDown(self):
        self.tmp.cleanup()

    def test_retryable_failure_requeues_then_succeeds(self):
        command_id = self.queue.enqueue("task", "create", '{"title":"buy milk"}', max_attempts=3)
        base = time.time()

        reserved = self.queue.reserve_next_ready(now=base)
        self.assertIsNotNone(reserved)
        self.assertEqual(reserved.id, command_id)
        self.assertEqual(reserved.status, "processing")

        status = self.queue.mark_failed(command_id, reason="timeout", retryable=True, backoff_seconds=30)
        self.assertEqual(status, "retrying")

        not_ready = self.queue.reserve_next_ready(now=base + 20)
        self.assertIsNone(not_ready)

        ready_again = self.queue.reserve_next_ready(now=base + 31)
        self.assertIsNotNone(ready_again)
        self.assertEqual(ready_again.id, command_id)

        self.queue.mark_succeeded(command_id)
        metrics = self.queue.metrics()
        self.assertEqual(metrics["succeeded"], 1)
        self.assertEqual(metrics["queue_depth"], 0)

    def test_non_retryable_failure_goes_to_dead_letter(self):
        command_id = self.queue.enqueue("email", "send", '{"to":"a@example.com"}')
        base = time.time()
        reserved = self.queue.reserve_next_ready(now=base)
        self.assertIsNotNone(reserved)

        status = self.queue.mark_failed(command_id, reason="auth", retryable=False)
        self.assertEqual(status, "dead_letter")

        dead_letters = self.queue.list_dead_letters()
        self.assertEqual(len(dead_letters), 1)
        self.assertEqual(dead_letters[0].id, command_id)
        self.assertEqual(dead_letters[0].last_error, "auth")

    def test_retryable_eventually_dead_letters_when_attempt_limit_reached(self):
        command_id = self.queue.enqueue("calendar", "create_event", '{"title":"sync"}', max_attempts=2)
        base = time.time()

        first = self.queue.reserve_next_ready(now=base)
        self.assertIsNotNone(first)
        self.assertEqual(self.queue.mark_failed(command_id, "upstream", retryable=True, backoff_seconds=1), "retrying")

        second = self.queue.reserve_next_ready(now=base + 2)
        self.assertIsNotNone(second)
        self.assertEqual(self.queue.mark_failed(command_id, "upstream", retryable=True, backoff_seconds=1), "dead_letter")

        metrics = self.queue.metrics()
        self.assertEqual(metrics["dead_letter"], 1)
        self.assertEqual(metrics["total_retries"], 2)


if __name__ == "__main__":
    unittest.main()
