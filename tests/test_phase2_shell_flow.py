import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test")

import pygame

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from screens.boot import BootScreen
from screens.lock import LockScreen
from screens.panels.home import HomePanel
from screens.manager import ScreenManager


class Phase2ShellFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_boot_auto_advances_after_three_seconds(self):
        triggered = {"called": False}

        def on_complete():
            triggered["called"] = True

        boot = BootScreen(on_complete=on_complete)
        boot._diagnostics.ensure_critical_results = lambda: None
        boot._diagnostics.all_critical_passed = lambda: True

        boot.update(3.1)
        self.assertTrue(triggered["called"])

    def test_lock_unlock_action(self):
        unlocked = {"called": False}

        def on_home():
            unlocked["called"] = True

        lock = LockScreen(on_home=on_home)
        lock.handle_action("SHORT_PRESS")
        self.assertTrue(unlocked["called"])

    def test_home_short_press_opens_chat(self):
        opened = {"called": False}

        def on_open_chat():
            opened["called"] = True

        home = HomePanel(on_open_chat=on_open_chat)
        home.handle_action("SHORT_PRESS")
        self.assertTrue(opened["called"])

    def test_home_navigation_focus_and_activation(self):
        opened = {"chat": 0, "focus": 0, "notifs": 0, "settings": 0}

        def on_open_chat():
            opened["chat"] += 1

        def on_open_focus():
            opened["focus"] += 1

        def on_open_notifications():
            opened["notifs"] += 1

        def on_open_settings():
            opened["settings"] += 1

        home = HomePanel(
            on_open_chat=on_open_chat,
            on_open_focus=on_open_focus,
            on_open_notifications=on_open_notifications,
            on_open_settings=on_open_settings,
        )

        # Default focus is CHAT and should activate.
        home.handle_action("SHORT_PRESS")
        self.assertEqual(opened["chat"], 1)

        # Move focus to FOCUS and activate.
        home.handle_action("LONG_PRESS")
        home.handle_action("SHORT_PRESS")
        self.assertEqual(opened["focus"], 1)

        # Move focus to NOTIFS and activate.
        home.handle_action("LONG_PRESS")
        home.handle_action("SHORT_PRESS")
        self.assertEqual(opened["notifs"], 1)

        # Move focus to SETTINGS and activate.
        home.handle_action("LONG_PRESS")
        home.handle_action("SHORT_PRESS")
        self.assertEqual(opened["settings"], 1)

        # Triple press should wrap backwards to NOTIFS and activate.
        home.handle_action("TRIPLE_PRESS")
        home.handle_action("SHORT_PRESS")
        self.assertEqual(opened["notifs"], 2)

    def test_home_keyboard_nav_changes_focus(self):
        opened = {"called": 0}

        def on_open_chat():
            opened["called"] += 1

        home = HomePanel(on_open_chat=on_open_chat)

        down = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_DOWN})
        enter = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_RETURN})
        up = pygame.event.Event(pygame.KEYDOWN, {"key": pygame.K_UP})

        home.handle_input(down)
        home.handle_input(enter)
        self.assertEqual(opened["called"], 0)

        home.handle_input(up)
        home.handle_input(enter)
        self.assertEqual(opened["called"], 1)

    def test_screen_manager_forwards_button_action(self):
        class ActionScreen:
            def __init__(self):
                self.last_action = None

            def on_enter(self):
                pass

            def on_exit(self):
                pass

            def update(self, dt):
                pass

            def render(self, surface):
                pass

            def handle_input(self, event):
                pass

            def handle_action(self, action):
                self.last_action = action

        mgr = ScreenManager()
        screen = ActionScreen()
        mgr.push(screen)
        mgr.handle_action("DOUBLE_PRESS")
        self.assertEqual(screen.last_action, "DOUBLE_PRESS")


if __name__ == "__main__":
    unittest.main()
