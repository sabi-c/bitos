"""Tests for IdleManager display sleep logic."""
import unittest
from unittest.mock import MagicMock


class TestIdleManager(unittest.TestCase):
    def _make(self, timeout=60):
        from power.idle import IdleManager

        driver = MagicMock()
        repo = MagicMock()
        repo.get_setting = MagicMock(return_value=timeout)
        mgr = IdleManager(driver, repo, default_timeout=timeout)
        return mgr, driver, repo

    def test_starts_awake(self):
        mgr, driver, _ = self._make()
        self.assertEqual(mgr.state, "awake")

    def test_dims_after_timeout(self):
        import time
        mgr, driver, _ = self._make(timeout=1)
        mgr._last_activity = time.time() - 2  # 2s ago, timeout=1s
        mgr.tick()
        self.assertEqual(mgr.state, "dim")
        driver.set_brightness.assert_called_with(30)

    def test_sleeps_after_double_timeout(self):
        import time
        mgr, driver, _ = self._make(timeout=1)
        mgr._last_activity = time.time() - 3  # 3s ago, timeout*2=2s
        mgr._state = "dim"
        mgr.tick()
        self.assertEqual(mgr.state, "sleep")
        driver.set_brightness.assert_called_with(0)

    def test_wake_restores_brightness(self):
        import time
        mgr, driver, _ = self._make(timeout=1)
        mgr._last_activity = time.time() - 2
        mgr.tick()
        self.assertEqual(mgr.state, "dim")
        mgr.wake()
        self.assertEqual(mgr.state, "awake")
        driver.set_brightness.assert_called_with(100)

    def test_never_sleep_when_timeout_zero(self):
        import time
        mgr, driver, _ = self._make(timeout=0)
        mgr._last_activity = time.time() - 9999
        mgr.tick()
        self.assertEqual(mgr.state, "awake")

    def test_no_brightness_call_when_already_at_level(self):
        mgr, driver, _ = self._make(timeout=60)
        mgr.tick()  # still awake, brightness already 100
        driver.set_brightness.assert_not_called()


if __name__ == "__main__":
    unittest.main()
