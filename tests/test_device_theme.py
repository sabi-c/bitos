import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from display.theme import merge_runtime_ui_settings, ui_font_size


class DeviceThemeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_merge_runtime_ui_settings_defaults(self):
        merged = merge_runtime_ui_settings(None)
        self.assertEqual(merged["font_family"], "press_start_2p")
        self.assertEqual(merged["font_size_overrides"]["body"], 8)

    def test_scaled_font_size(self):
        merged = merge_runtime_ui_settings({"font_scale": 1.5, "font_size_overrides": {"body": 10}})
        self.assertEqual(ui_font_size("body", merged), 15)


if __name__ == "__main__":
    unittest.main()
