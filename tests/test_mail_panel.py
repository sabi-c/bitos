import os
import unittest
from pathlib import Path
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "device"))

from screens.panels.mail import MailPanel


class _Client:
    def get_mail_inbox(self):
        return [
            {
                "thread_id": "thr_work_001",
                "sender": "Joaquin Rivera",
                "subject": "Invoice #4821 missing attachment",
                "timestamp": "9:12 AM",
                "unread": True,
            },
            {
                "thread_id": "thr_personal_001",
                "sender": "Anthony",
                "subject": "Sunday family lunch",
                "timestamp": "Yesterday",
                "unread": False,
            },
        ]

    def get_mail_thread(self, thread_id: str):
        return [
            {"from_me": False, "sender": "Joaquin Rivera", "text": "Did you get my email?", "timestamp": "Yesterday"},
            {"from_me": True, "sender": "Me", "text": "Resending now.", "timestamp": "Yesterday"},
        ]

    def draft_mail_reply(self, thread_id: str, transcript: str) -> str:
        return "Absolutely — I will resend the PDF shortly."

    def create_mail_draft(self, thread_id: str, body: str, confirmed=False) -> str:
        return "mock_draft_001" if confirmed else ""


class MailPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _panel(self):
        panel = MailPanel(client=_Client())
        panel._loading = False
        panel._threads = _Client().get_mail_inbox()
        return panel

    def test_mail_panel_renders_list_with_mock_data(self):
        panel = self._panel()
        surface = pygame.Surface((240, 280))
        panel.render(surface)
        self.assertEqual(panel._state, panel.STATE_LIST)
        self.assertEqual(len(panel._threads), 2)

    def test_short_press_scrolls_focus(self):
        panel = self._panel()
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._focused_idx, 1)

    def test_long_on_list_moves_to_thread(self):
        panel = self._panel()
        panel.handle_action("LONG_PRESS")
        self.assertEqual(panel._state, panel.STATE_THREAD)

    def test_long_on_thread_moves_to_draft_voice(self):
        panel = self._panel()
        panel.handle_action("LONG_PRESS")
        panel.handle_action("LONG_PRESS")
        self.assertEqual(panel._state, panel.STATE_DRAFT_VOICE)

    def test_double_on_thread_moves_to_list(self):
        panel = self._panel()
        panel.handle_action("LONG_PRESS")
        panel.handle_action("DOUBLE_PRESS")
        self.assertEqual(panel._state, panel.STATE_LIST)

    def test_double_on_confirm_moves_to_thread(self):
        panel = self._panel()
        panel._state = panel.STATE_CONFIRM
        panel.handle_action("DOUBLE_PRESS")
        self.assertEqual(panel._state, panel.STATE_THREAD)

    def test_render_thread_shows_subject_line(self):
        panel = self._panel()
        panel.handle_action("LONG_PRESS")
        surface = pygame.Surface((240, 280))
        panel.render(surface)
        self.assertTrue(panel._selected_subject.startswith("Invoice"))

    def test_render_confirm_uses_save_draft_not_send(self):
        panel = self._panel()
        panel._state = panel.STATE_CONFIRM
        panel._selected_sender = "Joaquin Rivera"
        panel._draft_text = "Draft text"
        surface = pygame.Surface((240, 280))
        panel.render(surface)
        self.assertIn("SAVE DRAFT", " | ".join(panel.CONFIRM_HINT_ROWS))
        self.assertNotIn("SEND", " | ".join(panel.CONFIRM_HINT_ROWS))


if __name__ == "__main__":
    unittest.main()
