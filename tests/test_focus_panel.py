import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from screens.panels.focus import FocusPanel


class FocusPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_start_pause_reset_flow(self):
        panel = FocusPanel(duration_seconds=120)
        self.assertFalse(panel.is_running)
        self.assertEqual(panel.remaining_seconds, 120)

        panel.handle_action("SHORT_PRESS")  # START
        self.assertTrue(panel.is_running)

        panel.update(1.2)
        self.assertEqual(panel.remaining_seconds, 119)

        panel.handle_action("SHORT_PRESS")  # PAUSE
        self.assertFalse(panel.is_running)

        panel.handle_action("LONG_PRESS")  # move to RESET
        panel.handle_action("SHORT_PRESS")  # activate RESET
        self.assertEqual(panel.remaining_seconds, 120)
        self.assertFalse(panel.is_running)

    def test_back_action_invokes_callback(self):
        called = {"count": 0}

        def on_back():
            called["count"] += 1

        panel = FocusPanel(on_back=on_back)
        panel.handle_action("DOUBLE_PRESS")  # DOUBLE_PRESS = back

        self.assertEqual(called["count"], 1)

    def test_timer_stops_at_zero(self):
        panel = FocusPanel(duration_seconds=61)
        panel.handle_action("SHORT_PRESS")

        panel.update(70.0)

        self.assertEqual(panel.remaining_seconds, 0)
        self.assertFalse(panel.is_running)


if __name__ == "__main__":
    unittest.main()
