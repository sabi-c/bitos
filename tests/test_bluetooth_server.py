import os
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from bluetooth.auth import AuthManager
from bluetooth.server import MockGATTServer, get_gatt_server


class BluetoothServerTests(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def _auth(self):
        return AuthManager(pin_hash="x", device_serial="s", ble_secret="11" * 32)

    def test_mock_gatt_server_starts_and_stops(self):
        server = MockGATTServer(auth_manager=self._auth())
        server.start()
        server.stop()

    def test_mock_set_discoverable_does_not_crash(self):
        server = MockGATTServer(auth_manager=self._auth())
        server.set_discoverable(True, timeout_s=120)
        server.set_discoverable(False)

    def test_get_gatt_server_returns_mock_when_env_mock(self):
        os.environ["BITOS_BLUETOOTH"] = "mock"
        server = get_gatt_server(auth_manager=self._auth())
        self.assertIsInstance(server, MockGATTServer)

    def test_notify_device_status_on_mock_no_error(self):
        server = MockGATTServer(auth_manager=self._auth())
        server.notify_device_status({"state": "ok"})


if __name__ == "__main__":
    unittest.main()
