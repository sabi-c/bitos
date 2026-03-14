import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from screens.panels.chat import ChatPanel
from storage.repository import DeviceRepository


class _NoopClient:
    def chat(self, _message):
        return iter([""])


class ChatQueueStatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_queue_status_copy_without_repository_is_blank(self):
        panel = ChatPanel(_NoopClient())
        self.assertEqual(panel._queue_status_copy(), "")

    def test_queue_status_copy_shows_depth_and_dead_letter_reason(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DeviceRepository(db_path=str(Path(tmp) / "bitos.db"))
            repo.initialize()
            pending_id = repo.queue_enqueue_command("task", "create", '{"title":"a"}')
            repo.queue_mark_succeeded(pending_id)

            dead_id = repo.queue_enqueue_command("task", "create", '{"title":"b"}')
            repo.queue_reserve_next_ready(now=10**12)
            repo.queue_mark_failed(dead_id, reason="auth_failed", retryable=False, backoff_seconds=0)

            panel = ChatPanel(_NoopClient(), repository=repo)
            copy = panel._queue_status_copy()
            self.assertIn("q:0", copy)
            self.assertIn("d:1", copy)
            self.assertIn("auth-fai", copy)


if __name__ == "__main__":
    unittest.main()
