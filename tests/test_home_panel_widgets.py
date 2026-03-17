"""Tests for enhanced HomePanel with widget strip and ticker."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from datetime import datetime

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from screens.panels.home import HomePanel


class HomePanelWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _make_panel(self, **kwargs):
        return HomePanel(**kwargs)

    def test_widget_strip_exists(self):
        panel = self._make_panel()
        self.assertIsNotNone(panel._widget_strip)
        self.assertEqual(len(panel._widget_strip.widgets), 3)

    def test_widget_keys(self):
        panel = self._make_panel()
        keys = [w.key for w in panel._widget_strip.widgets]
        self.assertEqual(keys, ["time", "weather", "unread"])

    def test_time_widget_updates(self):
        panel = self._make_panel()
        panel.update(0.1)
        time_w = [w for w in panel._widget_strip.widgets if w.key == "time"][0]
        expected = datetime.now().strftime("%H:%M")
        self.assertEqual(time_w.value, expected)

    def test_unread_widget_updates_from_status(self):
        status = MagicMock()
        status.imessage_unread = 3
        status.gmail_unread = 2
        panel = self._make_panel(status_state=status)
        panel.update(0.1)
        unread_w = [w for w in panel._widget_strip.widgets if w.key == "unread"][0]
        self.assertEqual(unread_w.value, "5")

    def test_unread_widget_zero_without_status(self):
        panel = self._make_panel()
        panel.update(0.1)
        unread_w = [w for w in panel._widget_strip.widgets if w.key == "unread"][0]
        self.assertEqual(unread_w.value, "0")

    def test_weather_widget_default(self):
        panel = self._make_panel()
        weather_w = [w for w in panel._widget_strip.widgets if w.key == "weather"][0]
        self.assertEqual(weather_w.value, "--")

    def test_render_with_widgets(self):
        """Render should not crash with widget strip."""
        panel = self._make_panel()
        surf = pygame.Surface((240, 280))
        panel.render(surf)

    def test_ticker_advances(self):
        panel = self._make_panel()
        panel._ticker_text = "HEADLINES: Test news item scrolling across the screen"
        panel.update(0.1)
        self.assertEqual(panel._ticker_offset, 1)
        panel.update(0.1)
        self.assertEqual(panel._ticker_offset, 2)

    def test_ticker_no_advance_when_empty(self):
        panel = self._make_panel()
        panel.update(0.1)
        self.assertEqual(panel._ticker_offset, 0)

    def test_render_with_ticker(self):
        """Render with ticker text should not crash."""
        panel = self._make_panel()
        panel._ticker_text = "Breaking: test headline"
        panel._ticker_offset = 50
        surf = pygame.Surface((240, 280))
        panel.render(surf)


if __name__ == "__main__":
    unittest.main()
