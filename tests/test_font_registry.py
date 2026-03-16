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


from display.theme import load_ui_font, flush_font_cache, _FONT_CACHE


class FontHotSwapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        flush_font_cache()

    def test_load_press_start(self):
        settings = {"font_family": "press_start_2p", "font_scale": 1.0,
                     "font_size_overrides": {"body": 12}}
        font = load_ui_font("body", settings)
        self.assertIsNotNone(font)

    def test_load_monocraft(self):
        settings = {"font_family": "monocraft", "font_scale": 1.0,
                     "font_size_overrides": {"body": 12}}
        font = load_ui_font("body", settings)
        self.assertIsNotNone(font)

    def test_different_families_return_different_fonts(self):
        ps = load_ui_font("body", {"font_family": "press_start_2p", "font_scale": 1.0,
                                    "font_size_overrides": {"body": 12}})
        mc = load_ui_font("body", {"font_family": "monocraft", "font_scale": 1.0,
                                    "font_size_overrides": {"body": 12}})
        self.assertIsNot(ps, mc)

    def test_flush_font_cache_clears_all(self):
        load_ui_font("body", {"font_family": "press_start_2p", "font_scale": 1.0,
                               "font_size_overrides": {"body": 12}})
        self.assertGreater(len(_FONT_CACHE), 0)
        flush_font_cache()
        self.assertEqual(len(_FONT_CACHE), 0)

    def test_unknown_family_falls_back_to_monospace(self):
        font = load_ui_font("body", {"font_family": "nonexistent_font", "font_scale": 1.0,
                                      "font_size_overrides": {"body": 12}})
        self.assertIsNotNone(font)


import tempfile
from storage.repository import DeviceRepository


class FontPickerPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = DeviceRepository(db_path=str(Path(self.tmp.name) / "bitos.db"))
        self.repo.initialize()
        self.went_back = False

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_font_is_press_start(self):
        from screens.panels.settings import FontPickerPanel
        panel = FontPickerPanel(repository=self.repo, on_back=lambda: None)
        self.assertEqual(panel._current_family, "press_start_2p")

    def test_short_press_cycles_font(self):
        from screens.panels.settings import FontPickerPanel
        panel = FontPickerPanel(repository=self.repo, on_back=lambda: None)
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._index, 1)

    def test_double_press_saves_and_goes_back(self):
        from screens.panels.settings import FontPickerPanel
        panel = FontPickerPanel(
            repository=self.repo,
            on_back=lambda: setattr(self, 'went_back', True),
        )
        panel.handle_action("SHORT_PRESS")  # monocraft
        panel.handle_action("DOUBLE_PRESS")  # select
        self.assertEqual(self.repo.get_setting("font_family", default="press_start_2p"), "monocraft")
        self.assertTrue(self.went_back)

    def test_long_press_goes_back_without_saving(self):
        from screens.panels.settings import FontPickerPanel
        panel = FontPickerPanel(
            repository=self.repo,
            on_back=lambda: setattr(self, 'went_back', True),
        )
        panel.handle_action("SHORT_PRESS")  # monocraft
        panel.handle_action("LONG_PRESS")  # back without saving
        self.assertEqual(self.repo.get_setting("font_family", default="press_start_2p"), "press_start_2p")
        self.assertTrue(self.went_back)


if __name__ == "__main__":
    unittest.main()
