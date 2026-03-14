import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

import main as server_main


class IntegrationStatusTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(server_main.app)

    def test_status_integrations_shape(self):
        resp = self.client.get("/status/integrations")
        self.assertEqual(resp.status_code, 200)
        payload = resp.json()
        self.assertIn("imessage", payload)
        self.assertIn("vikunja", payload)
        self.assertIn("ai", payload)

    def test_imessage_mock_without_password(self):
        with patch.dict(os.environ, {"BLUEBUBBLES_PASSWORD": ""}, clear=False):
            resp = self.client.get("/status/integrations")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["imessage"]["status"], "mock")

    def test_vikunja_mock_without_token(self):
        with patch.dict(os.environ, {"VIKUNJA_API_TOKEN": ""}, clear=False):
            resp = self.client.get("/status/integrations")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["vikunja"]["status"], "mock")

    def test_ai_offline_for_test_key(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-not-real"}, clear=False):
            resp = self.client.get("/status/integrations")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["ai"]["status"], "offline")

    def test_ai_online_for_sk_ant_key(self):
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-123"}, clear=False):
            resp = self.client.get("/status/integrations")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["ai"]["status"], "online")

    def test_post_settings_unknown_integration_400(self):
        resp = self.client.post("/settings/integrations", json={"integration": "unknown", "config": {}})
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
