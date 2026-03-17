"""Tests for Widget and WidgetStrip components."""
import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from screens.components.widgets import Widget, WidgetStrip
from display.theme import load_ui_font, merge_runtime_ui_settings


class WidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()
        cls._ui = merge_runtime_ui_settings(None)
        cls._fonts = {
            "hint": load_ui_font("hint", cls._ui),
            "small": load_ui_font("small", cls._ui),
        }

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_widget_creation(self):
        w = Widget(key="time", label="TIME", value="09:41")
        self.assertEqual(w.key, "time")
        self.assertEqual(w.label, "TIME")
        self.assertEqual(w.value, "09:41")
        self.assertEqual(w.subtitle, "")

    def test_widget_with_subtitle(self):
        w = Widget(key="weather", label="WEATHER", value="72F", subtitle="BURBANK")
        self.assertEqual(w.subtitle, "BURBANK")

    def test_widget_render_no_crash(self):
        surf = pygame.Surface((80, 50))
        w = Widget(key="time", label="TIME", value="09:41")
        w.render(surf, 0, 0, 80, 50, focused=False, fonts=self._fonts)
        w.render(surf, 0, 0, 80, 50, focused=True, fonts=self._fonts)

    def test_widget_render_without_fonts(self):
        """Render with no fonts should not crash."""
        surf = pygame.Surface((80, 50))
        w = Widget(key="x", label="X", value="1")
        w.render(surf, 0, 0, 80, 50)

    def test_widget_mutable_value(self):
        w = Widget(key="unread", label="UNREAD", value="0")
        w.value = "5"
        self.assertEqual(w.value, "5")


class WidgetStripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()
        cls._ui = merge_runtime_ui_settings(None)
        cls._fonts = {
            "hint": load_ui_font("hint", cls._ui),
            "small": load_ui_font("small", cls._ui),
        }

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _make_strip(self):
        return WidgetStrip([
            Widget(key="time", label="TIME", value="09:41"),
            Widget(key="weather", label="WEATHER", value="72F", subtitle="LA"),
            Widget(key="unread", label="UNREAD", value="3"),
        ])

    def test_focus_starts_at_zero(self):
        strip = self._make_strip()
        self.assertEqual(strip.focus_index, 0)

    def test_move_focus_right(self):
        strip = self._make_strip()
        strip.move_focus(1)
        self.assertEqual(strip.focus_index, 1)
        strip.move_focus(1)
        self.assertEqual(strip.focus_index, 2)

    def test_move_focus_wraps(self):
        strip = self._make_strip()
        strip.move_focus(-1)
        self.assertEqual(strip.focus_index, 2)

    def test_move_focus_wraps_forward(self):
        strip = self._make_strip()
        strip.move_focus(1)
        strip.move_focus(1)
        strip.move_focus(1)
        self.assertEqual(strip.focus_index, 0)

    def test_update_widget(self):
        strip = self._make_strip()
        result = strip.update_widget("weather", value="65F", subtitle="SF")
        self.assertTrue(result)
        w = [w for w in strip.widgets if w.key == "weather"][0]
        self.assertEqual(w.value, "65F")
        self.assertEqual(w.subtitle, "SF")

    def test_update_widget_missing_key(self):
        strip = self._make_strip()
        result = strip.update_widget("nonexistent", value="X")
        self.assertFalse(result)

    def test_update_widget_partial(self):
        strip = self._make_strip()
        strip.update_widget("time", value="10:00")
        w = [w for w in strip.widgets if w.key == "time"][0]
        self.assertEqual(w.value, "10:00")
        self.assertEqual(w.subtitle, "")  # unchanged

    def test_render_no_crash(self):
        strip = self._make_strip()
        surf = pygame.Surface((240, 50))
        strip.render(surf, 0, 240, 50, fonts=self._fonts)

    def test_render_empty_strip(self):
        strip = WidgetStrip([])
        surf = pygame.Surface((240, 50))
        strip.render(surf, 0, 240, 50, fonts=self._fonts)

    def test_move_focus_empty_strip(self):
        strip = WidgetStrip([])
        strip.move_focus(1)  # should not crash
        self.assertEqual(strip.focus_index, 0)


if __name__ == "__main__":
    unittest.main()
