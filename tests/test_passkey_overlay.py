import os
import unittest
from pathlib import Path
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from overlays.passkey import PasskeyOverlay
import display.tokens as tokens


class PasskeyOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_renders_without_crashing(self):
        overlay = PasskeyOverlay(code="123456", timeout_s=120)
        surface = pygame.Surface((240, 280))
        overlay.render(surface, tokens)

    def test_tick_returns_false_after_timeout(self):
        overlay = PasskeyOverlay(code="123456", timeout_s=1)
        self.assertFalse(overlay.tick(1200))

    def test_tick_returns_true_while_active(self):
        overlay = PasskeyOverlay(code="123456", timeout_s=2)
        self.assertTrue(overlay.tick(500))


if __name__ == "__main__":
    unittest.main()
