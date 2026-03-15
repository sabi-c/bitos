import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from client.api import BackendChatError
from screens.panels.chat import ChatPanel
from storage.repository import DeviceRepository


class _AlwaysOfflineClient:
    def chat(self, _message):
        raise BackendChatError("offline", "offline", retryable=True)


class _FailThenRecoverClient:
    def __init__(self):
        self.calls = 0

    def chat(self, _message):
        self.calls += 1
        if self.calls == 1:
            raise BackendChatError("timeout", "timed out", retryable=True)
        return iter(["recovered response"])


class _AuthFailureClient:
    def chat(self, _message):
        raise BackendChatError("auth", "bad key", retryable=False)


class ChatReliabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_offline_failure_sets_retryable_state(self):
        panel = ChatPanel(_AlwaysOfflineClient())
        panel._stream_response("hello")

        self.assertEqual(panel._status, panel.STATUS_OFFLINE)
        self.assertEqual(panel._status_detail, "Server offline")
        self.assertTrue(panel._can_retry())

    def test_retry_succeeds_without_restart(self):
        client = _FailThenRecoverClient()

        with tempfile.TemporaryDirectory() as tmp:
            repo = DeviceRepository(db_path=str(Path(tmp) / "bitos.db"))
            repo.initialize()
            panel = ChatPanel(client, repository=repo)
            panel._session_id = repo.create_session("Retry")

            panel._stream_response("hello")
            self.assertEqual(panel._status, panel.STATUS_DEGRADED)
            self.assertTrue(panel._can_retry())

            panel._retry_last_failed()
            for _ in range(200):
                if not panel._is_streaming:
                    break
                pygame.time.wait(5)

            self.assertEqual(panel._status, panel.STATUS_CONNECTED)
            self.assertFalse(panel._can_retry())
            self.assertIn("recovered response", panel._messages[-1]["text"])

    def test_non_retryable_error_hides_retry(self):
        panel = ChatPanel(_AuthFailureClient())
        panel._stream_response("hello")

        self.assertEqual(panel._status, panel.STATUS_DEGRADED)
        self.assertEqual(panel._status_detail, "auth failed")
        self.assertFalse(panel._can_retry())


if __name__ == "__main__":
    unittest.main()
