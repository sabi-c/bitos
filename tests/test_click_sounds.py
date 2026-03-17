"""Tests for ClickSoundPlayer audio feedback."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from audio.click_sounds import _generate_tone, _generate_ascending, ClickSoundPlayer


class ToneGenerationTests(unittest.TestCase):
    def test_generate_tone_returns_bytes(self):
        data = _generate_tone(1000, 2.0)
        self.assertIsInstance(data, bytes)
        self.assertGreater(len(data), 0)

    def test_generate_tone_length(self):
        """2ms at 44100 Hz = ~88 samples = ~176 bytes (int16)."""
        data = _generate_tone(1000, 2.0)
        n_samples = int(44100 * 2.0 / 1000.0)
        expected_bytes = n_samples * 2  # int16 = 2 bytes per sample
        self.assertEqual(len(data), expected_bytes)

    def test_generate_ascending_concatenates(self):
        single = _generate_tone(800, 15.0, fade_ms=1.0)
        double = _generate_ascending([800, 1200], step_ms=15.0)
        self.assertEqual(len(double), len(single) * 2)

    def test_generate_tone_zero_duration(self):
        data = _generate_tone(1000, 0.0)
        self.assertEqual(len(data), 0)


class ClickSoundPlayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        try:
            pygame.mixer.init(44100, -16, 1, 512)
        except pygame.error:
            pass

    @classmethod
    def tearDownClass(cls):
        try:
            pygame.mixer.quit()
        except Exception:
            pass
        pygame.quit()

    def test_disabled_does_not_play(self):
        player = ClickSoundPlayer(enabled=False)
        # Should not raise even if mixer is not ready
        player.play_tap()
        player.play_confirm()
        player.play_back()
        player.play_error()

    def test_enable_disable_toggle(self):
        player = ClickSoundPlayer(enabled=True)
        self.assertTrue(player.enabled)
        player.enabled = False
        self.assertFalse(player.enabled)
        player.enabled = True
        self.assertTrue(player.enabled)

    def test_set_volume_clamps(self):
        player = ClickSoundPlayer(volume=0.5)
        player.set_volume(2.0)
        self.assertEqual(player._volume, 1.0)
        player.set_volume(-1.0)
        self.assertEqual(player._volume, 0.0)

    def test_init_creates_four_sounds(self):
        player = ClickSoundPlayer(volume=0.12)
        if not pygame.mixer.get_init():
            self.skipTest("pygame.mixer not available")
        result = player._ensure_init()
        if not result:
            self.skipTest("mixer init failed in test env")
        self.assertEqual(len(player._sounds), 4)
        self.assertIn("tap", player._sounds)
        self.assertIn("back", player._sounds)
        self.assertIn("confirm", player._sounds)
        self.assertIn("error", player._sounds)

    def test_play_methods_do_not_crash(self):
        """All play methods should be safe to call even if mixer fails."""
        player = ClickSoundPlayer(volume=0.12)
        player.play_tap()
        player.play_confirm()
        player.play_back()
        player.play_error()

    def test_lazy_init(self):
        """Sounds are not created until first play."""
        player = ClickSoundPlayer()
        self.assertFalse(player._initialized)
        self.assertEqual(len(player._sounds), 0)

    def test_default_volume(self):
        player = ClickSoundPlayer()
        self.assertAlmostEqual(player._volume, 0.12)

    def test_mixer_not_init_returns_false(self):
        """If mixer is not initialized, _ensure_init returns False gracefully."""
        player = ClickSoundPlayer()
        with patch("pygame.mixer.get_init", return_value=None):
            result = player._ensure_init()
            self.assertFalse(result)
            self.assertFalse(player._initialized)


if __name__ == "__main__":
    unittest.main()
