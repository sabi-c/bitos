import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import httpx

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "device"))

from client.api import BackendClient
from screens.panels.chat import ChatPanel
from screens.panels.tasks import TasksPanel
from storage.repository import DeviceRepository


class _TimeoutStream:
    def __enter__(self):
        raise httpx.TimeoutException("timeout")

    def __exit__(self, exc_type, exc, tb):
        return False


class _ConnectStream:
    def __enter__(self):
        raise httpx.ConnectError("offline")

    def __exit__(self, exc_type, exc, tb):
        return False


class _OfflineClient:
    def chat(self, _message):
        return {"error": "Server offline", "kind": "offline", "retryable": True}


class _FailTasksClient:
    async def get_tasks(self):
        raise RuntimeError("boom")


class ErrorHandlingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_api_chat_returns_error_dict_on_connection_error(self):
        api = BackendClient(base_url="http://localhost:8000")
        with patch("client.api.httpx.stream", return_value=_ConnectStream()):
            result = api.chat("hello")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["error"], "Server offline")

    def test_api_chat_returns_error_dict_on_timeout(self):
        api = BackendClient(base_url="http://localhost:8000")
        with patch("client.api.httpx.stream", return_value=_TimeoutStream()):
            result = api.chat("hello")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["error"], "Server timeout")

    def test_chat_panel_shows_server_offline_on_connection_error(self):
        panel = ChatPanel(_OfflineClient())
        panel._stream_response("hello")
        self.assertEqual(panel._status_detail, "Server offline")

    def test_tasks_panel_offline_state_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DeviceRepository(db_path=str(Path(tmp) / "bitos.db"))
            repo.initialize()
            panel = TasksPanel(client=_FailTasksClient(), repository=repo)
            panel.on_enter()
            if panel._load_thread:
                panel._load_thread.join(timeout=1.0)
            self.assertEqual(panel._state, "offline")


if __name__ == "__main__":
    unittest.main()
