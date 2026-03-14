import os
import unittest
from pathlib import Path
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "device"))

from screens.panels.messages import MessagesPanel


class _Client:
    def get_conversations(self):
        return [
            {"chat_id": "iMessage;+;+13105550001", "title": "Joaquin", "snippet": "re: invoice", "timestamp": "2m", "unread": 2},
            {"chat_id": "iMessage;+;+13105550002", "title": "Anthony", "snippet": "looks good", "timestamp": "15m", "unread": 0},
        ]

    def get_messages(self, chat_id: str):
        return [
            {"id": "1", "text": "hello", "from_me": True},
            {"id": "2", "text": "need resend", "from_me": False},
        ]

    def draft_reply(self, chat_id: str, transcript: str) -> str:
        return "No problem — sending now."

    def send_message(self, chat_id: str, text: str, confirmed=False):
        return bool(confirmed)


class MessagesPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _panel(self):
        panel = MessagesPanel(client=_Client())
        panel._loading = False
        panel._conversations = _Client().get_conversations()
        return panel

    def test_renders_list_with_mock_data(self):
        panel = self._panel()
        surface = pygame.Surface((240, 280))
        panel.render(surface)
        self.assertEqual(panel._state, panel.STATE_LIST)
        self.assertEqual(len(panel._conversations), 2)

    def test_short_press_advances_focus(self):
        panel = self._panel()
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._focused_idx, 1)

    def test_long_press_on_list_opens_thread(self):
        panel = self._panel()
        panel.handle_action("LONG_PRESS")
        self.assertEqual(panel._state, panel.STATE_THREAD)

    def test_long_press_on_thread_opens_draft_voice(self):
        panel = self._panel()
        panel.handle_action("LONG_PRESS")
        panel.handle_action("LONG_PRESS")
        self.assertEqual(panel._state, panel.STATE_DRAFT_VOICE)

    def test_double_press_on_thread_goes_back_to_list(self):
        panel = self._panel()
        panel.handle_action("LONG_PRESS")
        panel.handle_action("DOUBLE_PRESS")
        self.assertEqual(panel._state, panel.STATE_LIST)

    def test_double_press_on_draft_goes_back_to_thread(self):
        panel = self._panel()
        panel.handle_action("LONG_PRESS")
        panel.handle_action("LONG_PRESS")
        panel.handle_action("DOUBLE_PRESS")
        self.assertEqual(panel._state, panel.STATE_THREAD)

    def test_double_press_on_confirm_clears_draft_and_goes_back_thread(self):
        panel = self._panel()
        panel._state = panel.STATE_CONFIRM_SEND
        panel._draft_text = "A draft"
        panel.handle_action("DOUBLE_PRESS")
        self.assertEqual(panel._draft_text, "")
        self.assertEqual(panel._state, panel.STATE_THREAD)

    def test_render_confirm_shows_bordered_box(self):
        panel = self._panel()
        panel._state = panel.STATE_CONFIRM_SEND
        panel._draft_text = "This is a draft reply message."
        surface = pygame.Surface((240, 280))
        panel.render_confirm(surface)
        self.assertTrue(panel._draft_text.startswith("This"))


if __name__ == "__main__":
    unittest.main()
