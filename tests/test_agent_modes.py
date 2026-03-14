import tempfile
import unittest
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from fastapi.testclient import TestClient

import main as server_main
from agent_modes import get_system_prompt
from ui_settings import UISettingsStore


class _CapturingBridge:
    provider = "capture"
    model = "capture-v1"

    def __init__(self):
        self.calls = []

    def stream_text(self, message: str, system_prompt: str | None = None):
        self.calls.append({"message": message, "system_prompt": system_prompt})
        yield "ok"


class AgentModePromptTests(unittest.TestCase):
    def test_get_system_prompt_producer_contains_expected_context(self):
        prompt = get_system_prompt("producer")
        self.assertIn("SSS", prompt)
        self.assertIn("Current mode: PRODUCER", prompt)

    def test_get_system_prompt_hacker_contains_expected_context(self):
        prompt = get_system_prompt("hacker")
        self.assertIn("BITOS", prompt)
        self.assertIn("Pi Zero 2W", prompt)

    def test_get_system_prompt_unknown_falls_back_to_producer(self):
        prompt = get_system_prompt("unknown")
        self.assertIn("Current mode: PRODUCER", prompt)
        self.assertIn("SSS", prompt)

    def test_get_system_prompt_includes_todays_date(self):
        prompt = get_system_prompt("producer")
        expected = date.today().strftime("%A, %B %d %Y")
        self.assertIn(expected, prompt)


class AgentModeServerWiringTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        settings_file = Path(self._tmp.name) / "ui_settings.json"
        server_main.settings_store = UISettingsStore(str(settings_file))
        self.bridge = _CapturingBridge()
        server_main.llm_bridge = self.bridge
        self.client = TestClient(server_main.app)

    def tearDown(self):
        self._tmp.cleanup()

    def test_chat_endpoint_accepts_agent_mode_field(self):
        with self.client.stream("POST", "/chat", json={"message": "hi", "agent_mode": "monk"}) as response:
            self.assertEqual(response.status_code, 200)
            _ = "".join(response.iter_text())

    def test_server_uses_correct_system_prompt_for_mode(self):
        with self.client.stream("POST", "/chat", json={"message": "hi", "agent_mode": "hacker"}) as response:
            self.assertEqual(response.status_code, 200)
            _ = "".join(response.iter_text())

        self.assertEqual(len(self.bridge.calls), 1)
        system_prompt = self.bridge.calls[0]["system_prompt"]
        self.assertIsNotNone(system_prompt)
        assert system_prompt is not None
        self.assertIn("Current mode: HACKER", system_prompt)
        self.assertIn("Pi Zero 2W", system_prompt)


if __name__ == "__main__":
    unittest.main()
