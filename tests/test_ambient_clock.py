"""Tests for AmbientClockScreen and IdleManager ambient clock integration."""

import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))


class AmbientClockScreenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_screen_name(self):
        from screens.ambient_clock import AmbientClockScreen
        screen = AmbientClockScreen()
        self.assertEqual(screen.SCREEN_NAME, "AMBIENT_CLOCK")

    def test_owns_status_bar(self):
        from screens.ambient_clock import AmbientClockScreen
        screen = AmbientClockScreen()
        self.assertTrue(screen._owns_status_bar)

    def test_update_sets_clock_text(self):
        from screens.ambient_clock import AmbientClockScreen
        screen = AmbientClockScreen()
        self.assertEqual(screen._clock_text, "")
        screen.update(0.016)
        self.assertRegex(screen._clock_text, r"\d{2}:\d{2}")

    def test_update_sets_date_text(self):
        from screens.ambient_clock import AmbientClockScreen
        screen = AmbientClockScreen()
        screen.update(0.016)
        # Date should contain a day abbreviation
        self.assertTrue(any(d in screen._date_text for d in
                            ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]))

    def test_render_does_not_crash(self):
        from screens.ambient_clock import AmbientClockScreen
        from display.tokens import PHYSICAL_W, PHYSICAL_H
        screen = AmbientClockScreen()
        screen.update(0.016)
        surface = pygame.Surface((PHYSICAL_W, PHYSICAL_H))
        # Should not raise
        screen.render(surface)

    def test_draw_delegates_to_render(self):
        from screens.ambient_clock import AmbientClockScreen
        from display.tokens import PHYSICAL_W, PHYSICAL_H
        screen = AmbientClockScreen()
        screen.update(0.016)
        surface = pygame.Surface((PHYSICAL_W, PHYSICAL_H))
        screen.draw(surface)  # Should not raise

    def test_handle_action_is_noop(self):
        from screens.ambient_clock import AmbientClockScreen
        screen = AmbientClockScreen()
        # Should not raise or do anything
        screen.handle_action("SHORT_PRESS")
        screen.handle_action("DOUBLE_PRESS")
        screen.handle_action("LONG_PRESS")


class IdleManagerAmbientClockTests(unittest.TestCase):
    """Test IdleManager pushes/pops ambient clock screen."""

    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _make_idle_mgr(self, screen_manager=None, timeout=60):
        from power.idle import IdleManager
        driver = MagicMock()
        repo = MagicMock()
        repo.get_setting = MagicMock(return_value=str(timeout))
        return IdleManager(driver, repo, default_timeout=timeout,
                           screen_manager=screen_manager)

    def test_dim_pushes_ambient_clock(self):
        mgr_mock = MagicMock()
        idle = self._make_idle_mgr(screen_manager=mgr_mock, timeout=10)

        # Simulate idle for longer than timeout
        idle._last_activity = time.time() - 15
        idle.tick()

        self.assertEqual(idle.state, "dim")
        mgr_mock.push.assert_called_once()
        pushed_screen = mgr_mock.push.call_args[0][0]
        self.assertEqual(type(pushed_screen).__name__, "AmbientClockScreen")

    def test_wake_pops_ambient_clock(self):
        mgr_mock = MagicMock()
        idle = self._make_idle_mgr(screen_manager=mgr_mock, timeout=10)

        # First go to dim state
        idle._last_activity = time.time() - 15
        idle.tick()
        self.assertTrue(idle._ambient_clock_pushed)

        # Set current screen to be the ambient clock
        current_mock = MagicMock()
        type(current_mock).__name__ = "AmbientClockScreen"
        mgr_mock.current = current_mock

        # Wake up
        idle.wake()
        self.assertEqual(idle.state, "awake")
        mgr_mock.pop.assert_called_once()
        self.assertFalse(idle._ambient_clock_pushed)

    def test_no_screen_manager_does_not_crash(self):
        """IdleManager without screen_manager should still work (no push/pop)."""
        idle = self._make_idle_mgr(screen_manager=None, timeout=10)
        idle._last_activity = time.time() - 15
        idle.tick()
        self.assertEqual(idle.state, "dim")
        idle.wake()
        self.assertEqual(idle.state, "awake")

    def test_double_push_prevented(self):
        mgr_mock = MagicMock()
        idle = self._make_idle_mgr(screen_manager=mgr_mock, timeout=10)

        idle._last_activity = time.time() - 15
        idle.tick()
        self.assertEqual(mgr_mock.push.call_count, 1)

        # Manually call _push again — should be a no-op
        idle._push_ambient_clock()
        self.assertEqual(mgr_mock.push.call_count, 1)

    def test_timeout_zero_never_pushes(self):
        mgr_mock = MagicMock()
        idle = self._make_idle_mgr(screen_manager=mgr_mock, timeout=0)
        idle._last_activity = time.time() - 999
        idle.tick()
        mgr_mock.push.assert_not_called()


if __name__ == "__main__":
    unittest.main()
