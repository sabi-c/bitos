import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from fastapi.testclient import TestClient
import main as server_main
from llm_bridge import EchoBridge
from ui_settings import UISettingsStore
from endpoints import codex_remote
from codex_app_client import InMemoryCodexAppClient


class CodexRemoteEndpointsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        settings_file = Path(self._tmp.name) / "ui_settings.json"
        server_main.settings_store = UISettingsStore(str(settings_file))
        server_main.llm_bridge = EchoBridge()
        codex_remote.client = InMemoryCodexAppClient()
        self.client = TestClient(server_main.app)

    def tearDown(self):
        self._tmp.cleanup()

    def test_session_turn_events_happy_path(self):
        create = self.client.post("/api/codex/sessions")
        self.assertEqual(create.status_code, 200)
        session_id = create.json()["session_id"]

        turn = self.client.post(
            f"/api/codex/sessions/{session_id}/turns",
            json={"message": "hello codex", "require_approval": False},
        )
        self.assertEqual(turn.status_code, 200)
        self.assertEqual(turn.json()["status"], "completed")

        events = self.client.get(f"/api/codex/sessions/{session_id}/events")
        self.assertEqual(events.status_code, 200)
        event_types = [e["type"] for e in events.json()["events"]]
        self.assertIn("user_message", event_types)
        self.assertIn("assistant_message", event_types)

    def test_approval_flow_allow(self):
        create = self.client.post("/api/codex/sessions")
        session_id = create.json()["session_id"]

        turn = self.client.post(
            f"/api/codex/sessions/{session_id}/turns",
            json={"message": "send message", "require_approval": True},
        )
        self.assertEqual(turn.status_code, 200)
        self.assertEqual(turn.json()["status"], "awaiting_approval")
        approval_id = turn.json()["pending_approval_id"]
        self.assertTrue(approval_id)

        approve = self.client.post(f"/api/codex/approvals/{approval_id}", json={"decision": "allow"})
        self.assertEqual(approve.status_code, 200)
        self.assertEqual(approve.json()["status"], "approved")

        events = self.client.get(f"/api/codex/sessions/{session_id}/events")
        self.assertEqual(events.status_code, 200)
        event_types = [e["type"] for e in events.json()["events"]]
        self.assertIn("approval_requested", event_types)
        self.assertIn("approval_resolved", event_types)
        self.assertIn("assistant_message", event_types)

    def test_unknown_session_returns_404(self):
        response = self.client.get("/api/codex/sessions/missing/events")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "session_not_found")


if __name__ == "__main__":
    unittest.main()
