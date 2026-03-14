import tempfile
import unittest

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from integrations.permissions import CommandRequest, OutboundCommandService, PermissionDeniedError
from integrations.queue import OutboundCommandQueue
from storage.repository import DeviceRepository


class OutboundPermissionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        repo = DeviceRepository(db_path=str(Path(self.tmp.name) / "bitos.db"))
        repo.initialize()
        self.queue = OutboundCommandQueue(repo)
        self.service = OutboundCommandService(self.queue)

    def tearDown(self):
        self.tmp.cleanup()

    def test_submit_requires_explicit_confirmation(self):
        with self.assertRaises(PermissionDeniedError):
            self.service.submit(
                CommandRequest(
                    domain="task",
                    operation="create",
                    payload='{"title":"buy milk"}',
                    confirmed=False,
                )
            )
        self.assertEqual(self.queue.metrics()["queue_depth"], 0)

    def test_submit_enqueues_when_confirmed(self):
        command_id = self.service.submit(
            CommandRequest(
                domain="task",
                operation="create",
                payload='{"title":"buy milk"}',
                confirmed=True,
                max_attempts=4,
            )
        )
        self.assertGreater(command_id, 0)
        self.assertEqual(self.queue.metrics()["pending"], 1)


if __name__ == "__main__":
    unittest.main()
