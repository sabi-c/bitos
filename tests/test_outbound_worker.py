import json
import tempfile
import time
import unittest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from integrations.contracts import AdapterResult
from integrations.queue import OutboundCommandQueue
from integrations.worker import OutboundCommandWorker
from storage.repository import DeviceRepository


class _TaskAdapter:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def create_task(self, title: str, details: str | None = None) -> AdapterResult:
        self.calls.append((title, details))
        return self.results.pop(0)

    def complete_task(self, provider_task_id: str) -> AdapterResult:
        self.calls.append((provider_task_id, None))
        return self.results.pop(0)


class OutboundWorkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        repo = DeviceRepository(db_path=str(Path(self.tmp.name) / "bitos.db"))
        repo.initialize()
        self.queue = OutboundCommandQueue(repo)

    def tearDown(self):
        self.tmp.cleanup()

    def test_process_successful_command(self):
        adapter = _TaskAdapter([AdapterResult(success=True, external_id="abc")])
        worker = OutboundCommandWorker(self.queue, task_adapter=adapter)
        command_id = self.queue.enqueue("task", "create", json.dumps({"title": "buy milk"}))

        result = worker.process_once(now=time.time())
        self.assertIsNotNone(result)
        self.assertEqual(result.command_id, command_id)
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(adapter.calls, [("buy milk", None)])
        self.assertEqual(self.queue.metrics()["succeeded"], 1)

    def test_retryable_failure_goes_retrying_then_succeeds(self):
        adapter = _TaskAdapter([
            AdapterResult(success=False, reason="upstream", retryable=True),
            AdapterResult(success=True),
        ])
        worker = OutboundCommandWorker(self.queue, task_adapter=adapter, default_backoff_seconds=0.5)
        self.queue.enqueue("task", "create", json.dumps({"title": "buy milk"}), max_attempts=3)
        base = time.time()

        first = worker.process_once(now=base)
        self.assertIsNotNone(first)
        self.assertEqual(first.status, "retrying")

        too_soon = worker.process_once(now=base + 0.1)
        self.assertIsNone(too_soon)

        second = worker.process_once(now=base + 0.6)
        self.assertIsNotNone(second)
        self.assertEqual(second.status, "succeeded")
        self.assertEqual(self.queue.metrics()["succeeded"], 1)

    def test_non_retryable_or_invalid_payload_dead_letters(self):
        adapter = _TaskAdapter([AdapterResult(success=False, reason="auth", retryable=False)])
        worker = OutboundCommandWorker(self.queue, task_adapter=adapter)
        self.queue.enqueue("task", "create", json.dumps({"title": "buy milk"}), max_attempts=3)
        self.queue.enqueue("task", "create", "{not-json", max_attempts=3)

        first = worker.process_once(now=time.time())
        self.assertIsNotNone(first)
        self.assertEqual(first.status, "dead_letter")
        self.assertEqual(first.reason, "auth")

        second = worker.process_once(now=time.time())
        self.assertIsNotNone(second)
        self.assertEqual(second.status, "dead_letter")
        self.assertEqual(second.reason, "invalid_payload")

        self.assertEqual(self.queue.metrics()["dead_letter"], 2)


if __name__ == "__main__":
    unittest.main()
