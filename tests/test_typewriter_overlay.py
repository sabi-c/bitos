"""Tests for TestTypewriterOverlay — rendering, auto-dismiss, input handling."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

import pygame


class TestTypewriterOverlayTests(unittest.TestCase):
    """Test TestTypewriterOverlay lifecycle and behavior."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.surface = pygame.Surface((240, 280))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _make_overlay(self, text="Hello world", config=None, on_dismiss=None):
        from overlays.test_typewriter import TestTypewriterOverlay
        cfg = config or {"base_speed_ms": 10, "jitter_amount": 0.0}
        return TestTypewriterOverlay(text, cfg, on_dismiss or (lambda: None))

    def test_creates_without_error(self):
        overlay = self._make_overlay()
        self.assertIsNotNone(overlay)

    def test_renders_without_error(self):
        overlay = self._make_overlay()
        overlay.render(self.surface)
        # Should not raise

    def test_tick_advances_typewriter(self):
        overlay = self._make_overlay()
        overlay.tick(0.5)  # 500ms with 10ms base speed should reveal chars
        overlay.render(self.surface)

    def test_auto_dismiss_after_completion(self):
        dismissed = [False]

        def on_dismiss():
            dismissed[0] = True

        overlay = self._make_overlay(text="Hi", on_dismiss=on_dismiss)
        # Advance enough to finish typewriter (10ms base, no jitter)
        overlay.tick(1.0)  # finishes typing
        self.assertFalse(dismissed[0])  # not yet — needs 2s pause

        # Simulate time passing by calling tick with enough dt
        # The overlay uses time.time() for the 2s pause, so we need to patch or tick enough
        import time
        from unittest.mock import patch

        # Force the finished_at timestamp to be in the past
        overlay._finished_at = time.time() - 3.0
        overlay.tick(0.016)
        self.assertTrue(dismissed[0])

    def test_long_press_dismisses(self):
        dismissed = [False]

        def on_dismiss():
            dismissed[0] = True

        overlay = self._make_overlay(on_dismiss=on_dismiss)
        result = overlay.handle_action("LONG_PRESS")
        self.assertTrue(result)  # consumed the event
        self.assertTrue(dismissed[0])

    def test_other_actions_consumed(self):
        overlay = self._make_overlay()
        result = overlay.handle_action("SHORT_PRESS")
        self.assertTrue(result)  # all input consumed while overlay active

    def test_double_press_consumed(self):
        overlay = self._make_overlay()
        result = overlay.handle_action("DOUBLE_PRESS")
        self.assertTrue(result)

    def test_custom_config_applied(self):
        config = {
            "base_speed_ms": 100,
            "punctuation_multiplier": 2.5,
            "jitter_amount": 0.0,
            "common_speedup": 0.7,
            "rare_slowdown": 1.8,
        }
        overlay = self._make_overlay(config=config)
        self.assertEqual(overlay._config.base_speed_ms, 100.0)
        self.assertEqual(overlay._config.punctuation_multiplier, 2.5)
        self.assertEqual(overlay._config.rare_slowdown, 1.8)

    def test_renders_config_info(self):
        """Config info should be rendered at bottom of surface."""
        overlay = self._make_overlay(config={"base_speed_ms": 77, "jitter_amount": 0.22, "punctuation_multiplier": 1.5})
        overlay.render(self.surface)
        # If it rendered without error, the config info was drawn

    def test_instant_config_finishes_fast(self):
        dismissed = [False]

        def on_dismiss():
            dismissed[0] = True

        overlay = self._make_overlay(
            text="Hello",
            config={"base_speed_ms": 0, "jitter_amount": 0.0},
            on_dismiss=on_dismiss,
        )
        # With base_speed=0, TypewriterRenderer finishes instantly
        overlay.tick(0.016)
        # finished_at should be set now
        self.assertIsNotNone(overlay._finished_at)

    def test_no_dismiss_before_timeout(self):
        dismissed = [False]

        def on_dismiss():
            dismissed[0] = True

        overlay = self._make_overlay(text="X", config={"base_speed_ms": 5, "jitter_amount": 0.0},
                                     on_dismiss=on_dismiss)
        overlay.tick(1.0)  # finishes typing
        overlay.tick(0.5)  # only 0.5s after finish — not 2s yet
        self.assertFalse(dismissed[0])


if __name__ == "__main__":
    unittest.main()
