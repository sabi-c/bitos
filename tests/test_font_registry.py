"""Tests for font registry and multi-font support."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from display.tokens import FONT_REGISTRY, DEFAULT_FONT_FAMILY


class FontRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_registry_has_press_start(self):
        self.assertIn("press_start_2p", FONT_REGISTRY)

    def test_registry_has_monocraft(self):
        self.assertIn("monocraft", FONT_REGISTRY)

    def test_default_is_press_start(self):
        self.assertEqual(DEFAULT_FONT_FAMILY, "press_start_2p")

    def test_all_font_files_exist(self):
        for family, path in FONT_REGISTRY.items():
            full = Path(__file__).resolve().parents[1] / "device" / path
            self.assertTrue(full.exists(), f"Font file missing for {family}: {full}")

    def test_all_fonts_load_in_pygame(self):
        for family, path in FONT_REGISTRY.items():
            full = str(Path(__file__).resolve().parents[1] / "device" / path)
            font = pygame.font.Font(full, 12)
            self.assertIsNotNone(font)
            surface = font.render("TEST", False, (255, 255, 255))
            self.assertGreater(surface.get_width(), 0)


if __name__ == "__main__":
    unittest.main()
