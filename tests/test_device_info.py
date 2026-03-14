import json
import os
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from bluetooth.characteristics.device_info import DeviceInfoCharacteristic, _read_pi_serial


class DeviceInfoTests(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_readvalue_returns_json_bytes(self):
        ch = DeviceInfoCharacteristic()
        raw = ch.ReadValue({})
        data = json.loads(raw.decode())
        self.assertIn("serial", data)

    def test_payload_contains_required_fields(self):
        ch = DeviceInfoCharacteristic()
        data = json.loads(ch.ReadValue({}).decode())
        for key in ["serial", "version", "model", "ble_protocol_version", "companion_url"]:
            self.assertIn(key, data)

    @patch("builtins.open", side_effect=FileNotFoundError())
    def test_serial_fallback_when_cpuinfo_unavailable(self, _open):
        self.assertEqual(_read_pi_serial(), "DESKTOP-DEV-001")

    def test_companion_url_reflects_env_override(self):
        os.environ["BITOS_COMPANION_URL"] = "https://override.test"
        from importlib import reload
        import bluetooth.constants as constants
        import bluetooth.characteristics.device_info as device_info

        reload(constants)
        reload(device_info)
        data = json.loads(device_info.DeviceInfoCharacteristic().ReadValue({}).decode())
        self.assertEqual(data["companion_url"], "https://override.test")


if __name__ == "__main__":
    unittest.main()
