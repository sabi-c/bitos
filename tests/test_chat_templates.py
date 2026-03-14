import os
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from screens.panels.chat import ChatPanel


class _NoopClient:
    def chat(self, _message):
        return iter([""])


class ChatTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_no_messages_shows_templates(self):
        panel = ChatPanel(_NoopClient())
        self.assertTrue(panel._showing_templates())
        self.assertGreater(len(panel._templates), 0)

    def test_long_press_on_template_sends_message(self):
        panel = ChatPanel(_NoopClient())
        template_message = panel._templates[0]["message"]

        panel.handle_action("LONG_PRESS")

        self.assertEqual(panel._messages[0]["role"], "user")
        self.assertEqual(panel._messages[0]["text"], template_message)

    def test_templates_hidden_after_first_message(self):
        panel = ChatPanel(_NoopClient())

        panel.handle_action("LONG_PRESS")

        self.assertFalse(panel._showing_templates())


if __name__ == "__main__":
    unittest.main()
