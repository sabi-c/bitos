"""Tests for NotificationBanner interactive overlay."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from overlays.notification_banner import NotificationBanner


class NotificationBannerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _make_banner(self, **kwargs):
        return NotificationBanner(
            app=kwargs.get("app", "CLAUDE"),
            icon=kwargs.get("icon", "C"),
            message=kwargs.get("message", "Good morning! Here's your brief."),
            time_str=kwargs.get("time_str", "08:30"),
            was_sleeping=kwargs.get("was_sleeping", False),
            on_dismiss=kwargs.get("on_dismiss"),
            on_reply=kwargs.get("on_reply"),
        )

    def test_short_press_triggers_record_reply(self):
        replies = []
        banner = self._make_banner(on_reply=lambda mode: replies.append(mode))
        banner.handle_action("SHORT_PRESS")
        self.assertEqual(replies, ["record"])
        self.assertTrue(banner.dismissed)

    def test_hold_start_triggers_quick_talk(self):
        replies = []
        banner = self._make_banner(on_reply=lambda mode: replies.append(mode))
        banner.handle_action("HOLD_START")
        self.assertEqual(replies, ["quick_talk"])
        self.assertTrue(banner.dismissed)

    def test_double_press_dismisses_without_reply(self):
        replies = []
        dismissed = []
        banner = self._make_banner(
            on_reply=lambda mode: replies.append(mode),
            on_dismiss=lambda: dismissed.append(True),
        )
        banner.handle_action("DOUBLE_PRESS")
        self.assertEqual(replies, [])
        self.assertTrue(dismissed)
        self.assertTrue(banner.dismissed)

    def test_long_press_also_dismisses(self):
        dismissed = []
        banner = self._make_banner(on_dismiss=lambda: dismissed.append(True))
        banner.handle_action("LONG_PRESS")
        self.assertTrue(dismissed)

    def test_consumes_all_gestures_while_active(self):
        banner = self._make_banner()
        self.assertTrue(banner.handle_action("TRIPLE_PRESS"))
        self.assertTrue(banner.handle_action("HOLD_END"))
        self.assertFalse(banner.dismissed)  # consumed but not dismissed

    def test_does_not_consume_after_dismissed(self):
        banner = self._make_banner()
        banner.handle_action("DOUBLE_PRESS")
        self.assertFalse(banner.handle_action("SHORT_PRESS"))

    def test_tick_expires_after_duration(self):
        banner = self._make_banner()
        banner.duration_ms = 100
        self.assertTrue(banner.tick(50))
        self.assertFalse(banner.dismissed)
        self.assertFalse(banner.tick(60))
        self.assertTrue(banner.dismissed)

    def test_compact_render_when_screen_awake(self):
        banner = self._make_banner(was_sleeping=False)
        surface = pygame.Surface((240, 280))
        banner.render(surface)
        # Should not crash — compact strip rendered

    def test_full_banner_render_when_screen_was_sleeping(self):
        banner = self._make_banner(was_sleeping=True)
        surface = pygame.Surface((240, 280))
        banner.render(surface)
        # Should not crash — full centered card rendered

    def test_on_dismiss_callback_called_once(self):
        count = []
        banner = self._make_banner(on_dismiss=lambda: count.append(1))
        banner.handle_action("DOUBLE_PRESS")
        banner.handle_action("DOUBLE_PRESS")  # already dismissed
        self.assertEqual(len(count), 1)


if __name__ == "__main__":
    unittest.main()
