import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from fastapi.testclient import TestClient
import main as server_main
from ui_settings import UISettingsStore


class ServerSettingsApiTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        settings_file = Path(self._tmp.name) / "ui_settings.json"
        server_main.settings_store = UISettingsStore(str(settings_file))
        self.client = TestClient(server_main.app)

    def tearDown(self):
        self._tmp.cleanup()

    def test_catalog_endpoint_available(self):
        response = self.client.get("/settings/catalog")
        self.assertEqual(response.status_code, 200)
        self.assertIn("font_scale", response.json())

    def test_get_settings_defaults(self):
        response = self.client.get("/settings/ui")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["font_family"], "press_start_2p")

    def test_update_settings_valid_patch(self):
        response = self.client.put("/settings/ui", json={"font_scale": 1.1, "layout_density": "compact"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["font_scale"], 1.1)
        self.assertEqual(body["layout_density"], "compact")

    def test_update_settings_invalid_patch(self):
        response = self.client.put("/settings/ui", json={"font_scale": 10.0})
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
