import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from screens.panels.chat import ChatPanel, ChatMode, DEFAULT_TEMPLATES


class ChatTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _make_panel(self):
        client = MagicMock()
        client.chat.return_value = iter([""])
        return ChatPanel(client=client)

    def test_default_templates_populated(self):
        panel = self._make_panel()
        self.assertGreater(len(panel._templates), 0)
        self.assertEqual(panel._templates, list(DEFAULT_TEMPLATES))

    def test_action_menu_includes_templates(self):
        panel = self._make_panel()
        items = panel._action_items()
        labels = [i.get("label") for i in items]
        # Templates appear at start, followed by nav items
        self.assertIn(DEFAULT_TEMPLATES[0]["label"], labels)

    def test_entering_actions_mode(self):
        panel = self._make_panel()
        panel._mode = ChatMode.ACTIONS
        self.assertEqual(panel._mode, ChatMode.ACTIONS)


if __name__ == "__main__":
    unittest.main()
