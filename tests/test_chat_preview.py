"""Tests for ChatPreviewPanel greeting + response field."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from device.ui.panels.chat_preview import ChatPreviewPanel, CHAT_ITEMS


class ChatPreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_items_include_response_field(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        self.assertEqual(panel.items[0]["action"], "respond")
        self.assertEqual(panel.items[0]["label"], "RECORD")

    def test_items_include_back_to_main_menu(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        last = panel.items[-1]
        self.assertEqual(last["action"], "back")
        self.assertEqual(last["label"], "BACK TO MAIN MENU")

    def test_set_greeting_text(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        panel.set_greeting("good morning, 3 tasks today")
        self.assertEqual(panel._greeting_text, "good morning, 3 tasks today")

    def test_greeting_typewriter_created(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        panel.set_greeting("hello there")
        self.assertIsNotNone(panel._greeting_typewriter)

    def test_set_resume_subtext(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        panel.set_resume_info("morning brief", "2h ago")
        resume_item = next(i for i in panel.items if i["action"] == "resume_chat")
        self.assertIn("morning brief", resume_item.get("subtext", ""))

    def test_respond_action_fires_callback(self):
        cb = MagicMock()
        panel = ChatPreviewPanel(on_action=cb)
        panel.selected_index = 0
        panel.handle_action("DOUBLE_PRESS")
        cb.assert_called_once_with("respond")

    def test_starts_with_no_highlight(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        self.assertEqual(panel.selected_index, -1)

    def test_item_count(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        self.assertEqual(len(panel.items), 6)

    def test_items_are_deep_copied(self):
        """Subtext mutations on one panel instance must not leak to another."""
        panel_a = ChatPreviewPanel(on_action=MagicMock())
        panel_a.set_resume_info("chat A", "1h ago")
        panel_b = ChatPreviewPanel(on_action=MagicMock())
        resume_b = next(i for i in panel_b.items if i["action"] == "resume_chat")
        self.assertEqual(resume_b.get("subtext", ""), "")

    def test_greeting_truncated_to_max(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        long_text = "x" * 200
        panel.set_greeting(long_text)
        self.assertEqual(len(panel._greeting_text), 120)


if __name__ == "__main__":
    unittest.main()
