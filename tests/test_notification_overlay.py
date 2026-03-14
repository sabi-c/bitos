import unittest

import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

import pygame

from overlays.notification import NotificationQueue, NotificationToast
from screens.manager import ScreenManager


class _Screen:
    def __init__(self, calls):
        self.calls = calls

    def on_enter(self):
        pass

    def on_exit(self):
        pass

    def update(self, dt):
        pass

    def handle_input(self, event):
        pass

    def handle_action(self, action):
        pass

    def render(self, surface):
        self.calls.append("screen")


class NotificationOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_toast_renders_above_screen_call_order(self):
        calls = []
        mgr = ScreenManager()
        mgr.push(_Screen(calls))

        toast = NotificationToast(app="SMS", icon="S", message="hello", time_str="10:10")
        orig_render = toast.render

        def wrapped(surface, tokens):
            calls.append("toast")
            return orig_render(surface, tokens)

        toast.render = wrapped
        mgr.notification_queue.push(toast)

        surface = pygame.Surface((240, 280))
        mgr.render(surface)

        self.assertEqual(calls, ["screen", "toast"])

    def test_toast_expires_after_duration(self):
        q = NotificationQueue()
        q.push(NotificationToast(app="MAIL", icon="M", message="x", time_str="10:11", duration_ms=100))

        q.tick(50)
        self.assertIsNotNone(q.active)
        q.tick(60)
        self.assertIsNone(q.active)

    def test_short_press_dismisses_immediately(self):
        q = NotificationQueue()
        q.push(NotificationToast(app="TASK", icon="T", message="x", time_str="10:11"))
        consumed = q.handle_input("SHORT_PRESS")
        self.assertTrue(consumed)
        self.assertIsNone(q.active)

    def test_queue_processes_priority_order(self):
        q = NotificationQueue()
        q.push(NotificationToast(app="MAIL", icon="M", message="1", time_str="10", duration_ms=10))
        q.push(NotificationToast(app="SMS", icon="S", message="2", time_str="10", duration_ms=10))
        q.push(NotificationToast(app="CLAUDE", icon="C", message="3", time_str="10", duration_ms=10))

        self.assertEqual(q.active.app, "MAIL")
        q.tick(20)
        self.assertEqual(q.active.app, "CLAUDE")
        q.tick(20)
        self.assertEqual(q.active.app, "SMS")

    def test_queue_caps_at_three_and_drops_lowest_priority(self):
        q = NotificationQueue()
        q.push(NotificationToast(app="SMS", icon="S", message="1", time_str="10", duration_ms=1000))
        q.push(NotificationToast(app="MAIL", icon="M", message="2", time_str="10", duration_ms=1000))
        q.push(NotificationToast(app="TASK", icon="T", message="3", time_str="10", duration_ms=1000))
        q.push(NotificationToast(app="CLAUDE", icon="C", message="4", time_str="10", duration_ms=1000))
        q.push(NotificationToast(app="MAIL", icon="M", message="5", time_str="10", duration_ms=1000))

        self.assertEqual(len(q.queued), 3)
        queued_apps = [t.app for t in q.queued]
        combined = queued_apps + ([q.active.app] if q.active else [])
        self.assertIn("CLAUDE", combined)
        self.assertIn("TASK", combined)
        self.assertIn("SMS", combined)
        self.assertNotEqual(combined.count("MAIL"), 2)


if __name__ == "__main__":
    unittest.main()
