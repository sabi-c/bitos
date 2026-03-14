import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from bluetooth.wifi_manager import WiFiManager


class WiFiManagerTimeoutTests(unittest.TestCase):
    @patch("bluetooth.wifi_manager.logging.warning")
    @patch("bluetooth.wifi_manager.subprocess.run")
    def test_add_network_timeout_returns_false_and_logs_warning(self, mock_run, mock_warning):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["nmcli"], timeout=8)

        mgr = WiFiManager()
        ok = mgr.add_or_update_network("SSID", "pw", "WPA2", 100)

        self.assertFalse(ok)
        mock_warning.assert_called()

    @patch("bluetooth.wifi_manager.logging.warning")
    @patch("bluetooth.wifi_manager.subprocess.run")
    def test_connection_up_timeout_returns_false_and_logs_warning(self, mock_run, mock_warning):
        first = MagicMock(returncode=0, stderr="", stdout="")
        mock_run.side_effect = [first, subprocess.TimeoutExpired(cmd=["nmcli", "connection", "up"], timeout=8)]

        mgr = WiFiManager()
        ok = mgr.add_or_update_network("SSID", "pw", "WPA2", 100)

        self.assertFalse(ok)
        mock_warning.assert_called()

    @patch("bluetooth.wifi_manager.subprocess.run")
    def test_get_status_timeout_returns_safe_defaults(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["nmcli"], timeout=3)

        mgr = WiFiManager()
        status = mgr.get_status()

        self.assertEqual(
            status,
            {
                "connected": False,
                "ssid": "",
                "signal": "weak",
                "ip": "",
                "last_error": None,
            },
        )


if __name__ == "__main__":
    unittest.main()
