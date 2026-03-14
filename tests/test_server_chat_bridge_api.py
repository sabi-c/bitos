import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from fastapi.testclient import TestClient
import main as server_main
from llm_bridge import EchoBridge
from ui_settings import UISettingsStore


class ServerChatBridgeApiTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        settings_file = Path(self._tmp.name) / "ui_settings.json"
        server_main.settings_store = UISettingsStore(str(settings_file))
        server_main.llm_bridge = EchoBridge()
        self.client = TestClient(server_main.app)

    def tearDown(self):
        self._tmp.cleanup()

    def test_health_includes_provider(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["provider"], "echo")
        self.assertEqual(body["model"], "echo-v1")

    def test_chat_streams_bridge_chunks(self):
        with self.client.stream("POST", "/chat", json={"message": "test message"}) as response:
            self.assertEqual(response.status_code, 200)
            text = "".join(response.iter_text())
            self.assertIn("[echo]", text)
            self.assertIn("data: [DONE]", text)


if __name__ == "__main__":
    unittest.main()
