import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from client.api import BackendClient
from fastapi.testclient import TestClient
import main as server_main
from ui_settings import UISettingsStore


class _ResponseStub:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        return None


class DeviceAuthTests(unittest.TestCase):
    def setUp(self):
        self._env_backup = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env_backup)

    def test_api_client_sends_device_token_header_when_set(self):
        os.environ["BITOS_DEVICE_TOKEN"] = "token-abc"
        captured = {}

        def fake_get(url, timeout, headers):
            captured["headers"] = headers
            return _ResponseStub(status_code=200)

        client = BackendClient(base_url="http://example")
        with patch("client.api.httpx.get", side_effect=fake_get):
            ok = client.health()

        self.assertTrue(ok)
        self.assertEqual(captured["headers"].get("X-Device-Token"), "token-abc")

    def test_api_client_omits_header_when_token_empty(self):
        os.environ["BITOS_DEVICE_TOKEN"] = ""
        captured = {}

        def fake_get(url, timeout, headers):
            captured["headers"] = headers
            return _ResponseStub(status_code=200)

        client = BackendClient(base_url="http://example")
        with patch("client.api.httpx.get", side_effect=fake_get):
            client.get_settings_catalog()

        self.assertEqual(captured["headers"], {})

    def _server_client(self):
        tmp = tempfile.TemporaryDirectory()
        settings_file = Path(tmp.name) / "ui_settings.json"
        server_main.settings_store = UISettingsStore(str(settings_file))
        server_main._token_warning_logged = False
        client = TestClient(server_main.app)
        return tmp, client

    def test_server_middleware_returns_401_on_token_mismatch(self):
        os.environ["BITOS_DEVICE_TOKEN"] = "expected"
        tmp, client = self._server_client()
        try:
            response = client.get("/settings/ui", headers={"X-Device-Token": "wrong"})
            self.assertEqual(response.status_code, 401)
        finally:
            tmp.cleanup()

    def test_server_middleware_allows_when_token_matches(self):
        os.environ["BITOS_DEVICE_TOKEN"] = "expected"
        tmp, client = self._server_client()
        try:
            response = client.get("/settings/ui", headers={"X-Device-Token": "expected"})
            self.assertEqual(response.status_code, 200)
        finally:
            tmp.cleanup()

    def test_server_allows_health_without_token(self):
        os.environ["BITOS_DEVICE_TOKEN"] = "expected"
        tmp, client = self._server_client()
        try:
            response = client.get("/health")
            self.assertEqual(response.status_code, 200)
        finally:
            tmp.cleanup()

    def test_server_allows_all_when_token_not_set(self):
        os.environ.pop("BITOS_DEVICE_TOKEN", None)
        tmp, client = self._server_client()
        try:
            response = client.get("/settings/catalog")
            self.assertEqual(response.status_code, 200)
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
