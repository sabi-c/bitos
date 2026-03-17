"""Tests for VolumeOverlay HUD."""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

import unittest
import pygame

pygame.init()

from overlays.volume import VolumeOverlay, show_volume_overlay, DISMISS_MS


class VolumeOverlayTests(unittest.TestCase):

    def test_tick_returns_true_while_alive(self):
        ov = VolumeOverlay(50)
        self.assertTrue(ov.tick(100))
        self.assertTrue(ov.tick(500))

    def test_tick_returns_false_after_dismiss_timeout(self):
        ov = VolumeOverlay(50)
        self.assertTrue(ov.tick(DISMISS_MS - 1))
        self.assertFalse(ov.tick(2))

    def test_handle_input_always_passes_through(self):
        ov = VolumeOverlay(75)
        self.assertFalse(ov.handle_input("SHORT_PRESS"))
        self.assertFalse(ov.handle_input("DOUBLE_PRESS"))
        self.assertFalse(ov.handle_input("LONG_PRESS"))

    def test_update_resets_timer(self):
        ov = VolumeOverlay(50)
        ov.tick(DISMISS_MS - 100)
        ov.update(80)
        # Timer was reset, so another full duration should be needed
        self.assertTrue(ov.tick(DISMISS_MS - 100))

    def test_volume_clamped(self):
        ov = VolumeOverlay(150)
        self.assertEqual(ov._volume, 100)
        ov.update(-20)
        self.assertEqual(ov._volume, 0)

    def test_render_does_not_crash(self):
        """Smoke test: render at various volumes without raising."""
        surface = pygame.Surface((240, 280))

        class FakeTokens:
            PHYSICAL_W = 240
            PHYSICAL_H = 280
            FONT_PATH = None
            FONT_SIZES = {"body": 17, "small": 13}

        for vol in (0, 25, 50, 75, 100):
            ov = VolumeOverlay(vol)
            ov.render(surface, FakeTokens)

    def test_show_volume_overlay_creates_overlay(self):
        """show_volume_overlay should push_overlay on the screen manager."""

        class FakeMgr:
            _active_overlay = None
            pushed = None

            def push_overlay(self, ov):
                self.pushed = ov
                self._active_overlay = ov

        mgr = FakeMgr()
        show_volume_overlay(70, mgr)
        self.assertIsInstance(mgr.pushed, VolumeOverlay)
        self.assertEqual(mgr.pushed._volume, 70)

    def test_show_volume_overlay_reuses_existing(self):
        """If a VolumeOverlay is already active, update in place."""
        existing = VolumeOverlay(50)

        class FakeMgr:
            _active_overlay = existing
            pushed = None

            def push_overlay(self, ov):
                self.pushed = ov
                self._active_overlay = ov

        show_volume_overlay(80, FakeMgr)
        # Should NOT have pushed a new one
        self.assertIsNone(FakeMgr.pushed)
        # Should have updated the existing one
        self.assertEqual(existing._volume, 80)


if __name__ == "__main__":
    unittest.main()
