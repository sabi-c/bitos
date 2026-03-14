import os
import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "server" / "integrations"))

import main as server_main
from gmail_adapter import GmailAdapter, MOCK_INBOX, MOCK_THREADS


class GmailAdapterTests(unittest.TestCase):
    def setUp(self):
        self._old_enabled = os.environ.get("GMAIL_ENABLED")
        self._old_key = os.environ.get("ANTHROPIC_API_KEY")
        os.environ["GMAIL_ENABLED"] = "false"
        os.environ.pop("ANTHROPIC_API_KEY", None)

    def tearDown(self):
        if self._old_enabled is None:
            os.environ.pop("GMAIL_ENABLED", None)
        else:
            os.environ["GMAIL_ENABLED"] = self._old_enabled

        if self._old_key is None:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        else:
            os.environ["ANTHROPIC_API_KEY"] = self._old_key

    def test_mock_mode_get_inbox_returns_mock_inbox(self):
        adapter = GmailAdapter()
        self.assertEqual(adapter.get_inbox(), MOCK_INBOX)

    def test_mock_mode_get_thread_returns_mock_thread(self):
        adapter = GmailAdapter()
        self.assertEqual(adapter.get_thread("thr_work_001"), MOCK_THREADS["thr_work_001"])

    def test_mock_mode_get_unread_count_returns_two(self):
        adapter = GmailAdapter()
        self.assertEqual(adapter.get_unread_count(), 2)

    def test_mock_mode_create_draft_returns_mock_id(self):
        adapter = GmailAdapter()
        self.assertEqual(adapter.create_draft("thr_work_001", "Body"), "mock_draft_001")

    def test_mock_mode_draft_reply_returns_text(self):
        adapter = GmailAdapter()
        draft = adapter.draft_reply("thr_work_001", "Please resend")
        self.assertTrue(isinstance(draft, str))
        self.assertGreater(len(draft), 0)

    def test_gmail_disabled_forces_mock(self):
        os.environ["GMAIL_ENABLED"] = "false"
        adapter = GmailAdapter()
        self.assertTrue(adapter._mock)

    def test_test_api_key_forces_mock(self):
        os.environ["GMAIL_ENABLED"] = "true"
        os.environ["ANTHROPIC_API_KEY"] = "test-key-not-real"
        adapter = GmailAdapter()
        self.assertTrue(adapter._mock)

    def test_mail_endpoint_returns_threads_and_unread_total(self):
        client = TestClient(server_main.app)
        resp = client.get("/mail")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertIn("threads", payload)
        self.assertIn("unread_total", payload)

    def test_mail_draft_endpoint_returns_draft_string(self):
        client = TestClient(server_main.app)
        resp = client.post("/mail/draft", json={"thread_id": "thr_work_001", "voice_transcript": "Please resend"})
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(isinstance(resp.json().get("draft"), str))

    def test_mail_create_draft_requires_confirmed(self):
        client = TestClient(server_main.app)
        resp = client.post("/mail/create-draft", json={"thread_id": "thr_work_001", "body": "x", "confirmed": False})
        self.assertEqual(resp.status_code, 403)

    def test_mail_create_draft_confirmed_returns_ok_true(self):
        client = TestClient(server_main.app)
        resp = client.post("/mail/create-draft", json={"thread_id": "thr_work_001", "body": "x", "confirmed": True})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json().get("ok"), True)


if __name__ == "__main__":
    unittest.main()
