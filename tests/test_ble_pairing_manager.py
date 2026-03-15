"""Tests for BLE PairingManager resilience."""
import os
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from device.ble.pairing_manager import PairingManager


class PairingManagerTests(unittest.TestCase):
    def setUp(self):
        self._env = dict(os.environ)

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)

    def test_start_skipped_when_mock_env(self):
        os.environ["BITOS_BLE"] = "mock"
        mgr = PairingManager()
        mgr.start()
        # Should not start a thread
        self.assertFalse(mgr._running)
        self.assertIsNone(mgr._thread)

    @patch("device.ble.pairing_manager.shutil")
    def test_start_skipped_when_no_bluetoothctl(self, mock_shutil):
        mock_shutil.which.return_value = None
        os.environ.pop("BITOS_BLE", None)
        mgr = PairingManager()
        mgr._has_bluetoothctl = False
        mgr.start()
        self.assertFalse(mgr._running)
        self.assertIsNone(mgr._thread)

    def test_stop_without_start_no_crash(self):
        mgr = PairingManager()
        mgr.stop()

    def test_stop_with_none_ancs_client_no_crash(self):
        mgr = PairingManager()
        mgr._ancs_client = None
        mgr.stop()

    def test_on_notification_callback_stored(self):
        mgr = PairingManager()
        cb = lambda n: None
        mgr.on_notification(cb)
        self.assertIs(mgr._on_notif_cb, cb)

    @patch("device.ble.pairing_manager.subprocess")
    def test_get_paired_iphone_handles_filenotfounderror(self, mock_subprocess):
        mock_subprocess.run.side_effect = FileNotFoundError("no bluetoothctl")
        mgr = PairingManager()
        mgr._has_bluetoothctl = True
        result = mgr._get_paired_iphone()
        self.assertIsNone(result)
        self.assertFalse(mgr._has_bluetoothctl)

    @patch("device.ble.pairing_manager.subprocess")
    def test_get_paired_iphone_handles_timeout(self, mock_subprocess):
        import subprocess as real_subprocess
        mock_subprocess.run.side_effect = real_subprocess.TimeoutExpired(cmd="bluetoothctl", timeout=5)
        mgr = PairingManager()
        mgr._has_bluetoothctl = True
        result = mgr._get_paired_iphone()
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
