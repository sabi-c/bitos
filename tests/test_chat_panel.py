"""Tests for ChatPanel action menu and voice-first flow."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from screens.panels.chat import ChatPanel


class ChatActionMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()
        cls.surface = pygame.Surface((240, 280))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _make_panel(self, **kwargs):
        client = MagicMock()
        client.chat = MagicMock(return_value=iter(["hello"]))
        repo = MagicMock()
        repo.get_setting = MagicMock(return_value=None)
        repo.get_latest_session = MagicMock(return_value=None)
        return ChatPanel(client=client, repository=repo, on_back=kwargs.get("on_back"), audio_pipeline=kwargs.get("audio"))

    def test_action_menu_starts_at_speak(self):
        panel = self._make_panel()
        self.assertEqual(panel._action_index, 0)

    def test_short_press_cycles_action_menu(self):
        panel = self._make_panel()
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._action_index, 1)

    def test_short_press_wraps_around(self):
        panel = self._make_panel()
        for _ in range(3):
            panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._action_index, 0)

    def test_double_press_on_back_calls_on_back(self):
        called = []
        panel = self._make_panel(on_back=lambda: called.append(True))
        panel._action_index = 2  # BACK
        panel.handle_action("DOUBLE_PRESS")
        self.assertTrue(called)

    def test_long_press_always_goes_back(self):
        called = []
        panel = self._make_panel(on_back=lambda: called.append(True))
        panel.handle_action("LONG_PRESS")
        self.assertTrue(called)

    @unittest.skipIf(
        os.environ.get("SDL_VIDEODRIVER") == "dummy",
        "pygame segfaults rendering fonts with dummy video driver on macOS",
    )
    def test_render_without_error(self):
        panel = self._make_panel()
        panel.render(self.surface)

    def test_double_press_on_actions_toggles_submenu(self):
        panel = self._make_panel()
        panel._action_index = 1  # ACTIONS
        panel.handle_action("DOUBLE_PRESS")
        self.assertTrue(panel._showing_actions)

    def test_showing_actions_false_by_default(self):
        panel = self._make_panel()
        self.assertFalse(panel._showing_actions)


if __name__ == "__main__":
    unittest.main()
