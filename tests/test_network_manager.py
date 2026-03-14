import os
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from bluetooth.network_manager import NetworkPriorityManager


class NetworkManagerTests(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)
        os.environ["BITOS_WIFI"] = "mock"

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_mock_set_priority_returns_true(self):
        mgr = NetworkPriorityManager()
        self.assertTrue(mgr.set_priority("SSID", 100))

    def test_mock_active_connection_returns_none(self):
        mgr = NetworkPriorityManager()
        self.assertIsNone(mgr.get_active_connection())

    def test_mock_setup_bt_pan_profile_returns_true(self):
        mgr = NetworkPriorityManager()
        self.assertTrue(mgr.setup_bt_pan_profile())

    def test_connectivity_symbol_none(self):
        mgr = NetworkPriorityManager()
        self.assertEqual(mgr.get_connectivity_symbol(), "✕")


if __name__ == "__main__":
    unittest.main()
