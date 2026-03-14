import os
import unittest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

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
        boot.update(3.1)
        self.assertTrue(triggered["called"])

    def test_lock_unlock_action(self):
        unlocked = {"called": False}

        def on_unlock():
            unlocked["called"] = True

        lock = LockScreen(on_unlock=on_unlock)
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
        opened = {"called": 0}

        def on_open_chat():
            opened["called"] += 1

        home = HomePanel(on_open_chat=on_open_chat)

        # Default focus is CHAT and should activate.
        home.handle_action("SHORT_PRESS")
        self.assertEqual(opened["called"], 1)

        # Move focus to FOCUS (placeholder), selecting should not open chat.
        home.handle_action("DOUBLE_PRESS")
        home.handle_action("SHORT_PRESS")
        self.assertEqual(opened["called"], 1)

        # Triple press should wrap backwards to CHAT and activate again.
        home.handle_action("TRIPLE_PRESS")
        home.handle_action("SHORT_PRESS")
        self.assertEqual(opened["called"], 2)

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
