import os
import tempfile
import time
import unittest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from integrations.adapters import DisabledAdapter, EchoAdapter, create_runtime_adapter
from integrations.contracts import AdapterResult
from integrations.queue import OutboundCommandQueue
from integrations.runtime import OutboundWorkerRuntimeLoop
from integrations.worker import OutboundCommandWorker
from storage.repository import DeviceRepository


class _FlakyTaskAdapter:
    def __init__(self):
        self.calls = 0

    def create_task(self, title: str, details: str | None = None) -> AdapterResult:
        self.calls += 1
        if self.calls == 1:
            return AdapterResult(success=False, reason="upstream", retryable=True)
        return AdapterResult(success=True, external_id="ok")

    def complete_task(self, provider_task_id: str) -> AdapterResult:
        return AdapterResult(success=True)


class OutboundRuntimeLoopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        repo = DeviceRepository(db_path=str(Path(self.tmp.name) / "bitos.db"))
        repo.initialize()
        self.queue = OutboundCommandQueue(repo)

    def tearDown(self):
        self.tmp.cleanup()

    def test_runtime_loop_obeys_interval_and_max_per_tick(self):
        adapter = EchoAdapter()
        worker = OutboundCommandWorker(self.queue, task_adapter=adapter)
        loop = OutboundWorkerRuntimeLoop(worker, interval_seconds=0.2, max_per_tick=1)

        self.queue.enqueue("task", "create", '{"title":"a"}')
        self.queue.enqueue("task", "create", '{"title":"b"}')

        base = time.time() + 0.01
        first = loop.tick(now=base)
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0].status, "succeeded")

        blocked = loop.tick(now=base + 0.1)
        self.assertEqual(blocked, [])

        second = loop.tick(now=base + 0.21)
        self.assertEqual(len(second), 1)
        self.assertEqual(second[0].status, "succeeded")

    def test_runtime_loop_progresses_retry_to_success(self):
        adapter = _FlakyTaskAdapter()
        worker = OutboundCommandWorker(self.queue, task_adapter=adapter, default_backoff_seconds=0.3)
        loop = OutboundWorkerRuntimeLoop(worker, interval_seconds=0.1, max_per_tick=1)

        self.queue.enqueue("task", "create", '{"title":"buy milk"}', max_attempts=3)

        base = time.time() + 0.01
        first = loop.tick(now=base)
        self.assertEqual(len(first), 1)
        self.assertEqual(first[0].status, "retrying")

        too_soon = loop.tick(now=base + 0.2)
        self.assertEqual(too_soon, [])

        second = loop.tick(now=base + 0.4)
        self.assertEqual(len(second), 1)
        self.assertEqual(second[0].status, "succeeded")

    def test_runtime_adapter_factory_modes(self):
        previous = os.environ.get("BITOS_ADAPTER_MODE")
        try:
            os.environ["BITOS_ADAPTER_MODE"] = "echo"
            self.assertIsInstance(create_runtime_adapter(), EchoAdapter)

            os.environ["BITOS_ADAPTER_MODE"] = "disabled"
            self.assertIsInstance(create_runtime_adapter(), DisabledAdapter)
        finally:
            if previous is None:
                os.environ.pop("BITOS_ADAPTER_MODE", None)
            else:
                os.environ["BITOS_ADAPTER_MODE"] = previous


if __name__ == "__main__":
    unittest.main()
