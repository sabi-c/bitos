import os
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "server" / "integrations"))

from fastapi.testclient import TestClient

import main as server_main
from bluebubbles_adapter import BlueBubblesAdapter


class _FakeLLM:
    provider = "test"
    model = "test"

    def complete_text(self, prompt: str) -> str:
        return "Sounds good — I'll resend it now."

    def stream_text(self, prompt: str):
        yield "fallback"


class BlueBubblesAdapterTests(unittest.TestCase):
    def setUp(self):
        self._old_pw = os.environ.get("BLUEBUBBLES_PASSWORD")
        os.environ.pop("BLUEBUBBLES_PASSWORD", None)

    def tearDown(self):
        if self._old_pw is None:
            os.environ.pop("BLUEBUBBLES_PASSWORD", None)
        else:
            os.environ["BLUEBUBBLES_PASSWORD"] = self._old_pw

    def test_mock_conversations_returns_three_items(self):
        adapter = BlueBubblesAdapter()
        self.assertEqual(len(adapter.get_conversations()), 3)

    def test_mock_messages_returns_list(self):
        adapter = BlueBubblesAdapter()
        msgs = adapter.get_messages("iMessage;+;+13105550001")
        self.assertTrue(isinstance(msgs, list))
        self.assertGreater(len(msgs), 0)

    def test_mock_send_returns_true(self):
        adapter = BlueBubblesAdapter()
        self.assertTrue(adapter.send_message("iMessage;+;+13105550001", "hello"))

    def test_unread_count_in_mock_mode(self):
        adapter = BlueBubblesAdapter()
        self.assertEqual(adapter.get_unread_count(), 3)

    def test_missing_password_enables_mock(self):
        adapter = BlueBubblesAdapter()
        self.assertTrue(adapter._mock)

    def test_messages_endpoint_returns_conversations_and_unread_total(self):
        client = TestClient(server_main.app)
        resp = client.get("/messages")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertIn("conversations", payload)
        self.assertIn("unread_total", payload)

    def test_send_requires_confirmed_true(self):
        client = TestClient(server_main.app)
        resp = client.post("/messages/send", json={"chat_id": "iMessage;+;+13105550001", "text": "x", "confirmed": False})
        self.assertEqual(resp.status_code, 403)

    def test_send_with_confirmed_true_returns_sent(self):
        client = TestClient(server_main.app)
        resp = client.post("/messages/send", json={"chat_id": "iMessage;+;+13105550001", "text": "x", "confirmed": True})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"sent": True})

    def test_draft_returns_string(self):
        client = TestClient(server_main.app)
        original = server_main.llm_bridge
        server_main.llm_bridge = _FakeLLM()
        try:
            resp = client.post(
                "/messages/draft",
                json={"chat_id": "iMessage;+;+13105550001", "voice_transcript": "tell him I can resend"},
            )
        finally:
            server_main.llm_bridge = original
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(isinstance(resp.json().get("draft"), str))

    def test_webhook_ignores_non_new_message_events(self):
        client = TestClient(server_main.app)
        resp = client.post("/webhooks/imessage", json={"event": "typing", "data": {}})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), {"ok": True})


if __name__ == "__main__":
    unittest.main()
