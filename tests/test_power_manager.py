"""Tests for PowerManager adaptive FPS and power control."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from power.manager import PowerManager


class TestPowerManager(unittest.TestCase):

    def test_starts_active(self):
        pm = PowerManager()
        self.assertFalse(pm.should_dim())
        self.assertFalse(pm.should_sleep())

    def test_get_target_fps_active(self):
        pm = PowerManager(fps_active=15, fps_idle=5)
        self.assertEqual(pm.get_target_fps(), 15)

    def test_get_target_fps_idle(self):
        pm = PowerManager(dim_after=1, fps_active=15, fps_idle=5)
        pm._last_activity -= 2  # simulate 2s idle
        self.assertEqual(pm.get_target_fps(), 5)

    def test_should_dim_after_timeout(self):
        pm = PowerManager(dim_after=1)
        pm._last_activity -= 2
        self.assertTrue(pm.should_dim())

    def test_should_not_dim_when_disabled(self):
        pm = PowerManager(dim_after=0)
        pm._last_activity -= 9999
        self.assertFalse(pm.should_dim())

    def test_should_sleep_after_timeout(self):
        pm = PowerManager(sleep_after=2)
        pm._last_activity -= 3
        self.assertTrue(pm.should_sleep())

    def test_should_not_sleep_when_disabled(self):
        pm = PowerManager(sleep_after=0)
        pm._last_activity -= 9999
        self.assertFalse(pm.should_sleep())

    def test_poke_resets_timers(self):
        pm = PowerManager(dim_after=1, sleep_after=2)
        pm._last_activity -= 10
        self.assertTrue(pm.should_dim())
        self.assertTrue(pm.should_sleep())
        pm.poke()
        self.assertFalse(pm.should_dim())
        self.assertFalse(pm.should_sleep())

    def test_idle_seconds(self):
        pm = PowerManager()
        pm._last_activity -= 5
        self.assertGreaterEqual(pm.idle_seconds, 4.9)

    def test_system_power_save_noop_on_macos(self):
        pm = PowerManager()
        pm._is_linux = False
        # Should not raise — just a no-op
        pm.system_power_save()

    @patch("power.manager.subprocess.run")
    def test_system_power_save_runs_commands_on_linux(self, mock_run):
        pm = PowerManager()
        pm._is_linux = True
        pm.system_power_save()
        self.assertEqual(mock_run.call_count, 3)
        # Check commands executed
        calls = [c.args[0] for c in mock_run.call_args_list]
        self.assertEqual(calls[0], ["tvservice", "-o"])
        self.assertEqual(calls[1], ["rfkill", "block", "bluetooth"])
        self.assertEqual(calls[2], ["iwconfig", "wlan0", "power", "on"])

    @patch("power.manager.subprocess.run")
    def test_wifi_power_save_toggle(self, mock_run):
        pm = PowerManager()
        pm._is_linux = True
        pm.wifi_power_save(enable=False)
        mock_run.assert_called_once()
        cmd = mock_run.call_args.args[0]
        self.assertEqual(cmd, ["iwconfig", "wlan0", "power", "off"])

    def test_wifi_power_save_noop_on_macos(self):
        pm = PowerManager()
        pm._is_linux = False
        pm.wifi_power_save(enable=True)  # should not raise

    def test_fps_values_clamped(self):
        pm = PowerManager(fps_active=0, fps_idle=-5)
        self.assertGreaterEqual(pm.fps_active, 1)
        self.assertGreaterEqual(pm.fps_idle, 1)

    def test_dim_before_sleep(self):
        """Dim timeout should trigger before sleep timeout."""
        pm = PowerManager(dim_after=10, sleep_after=30)
        pm._last_activity -= 15  # 15s idle
        self.assertTrue(pm.should_dim())
        self.assertFalse(pm.should_sleep())

    @patch("power.manager.subprocess.run", side_effect=FileNotFoundError)
    def test_system_power_save_handles_missing_commands(self, mock_run):
        pm = PowerManager()
        pm._is_linux = True
        # Should not raise even if commands don't exist
        pm.system_power_save()


if __name__ == "__main__":
    unittest.main()
