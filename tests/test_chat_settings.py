"""Tests for ChatSettingsPanel."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from screens.panels.chat_settings import ChatSettingsPanel


class ChatSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_has_meta_prompt_setting(self):
        repo = MagicMock()
        repo.get_setting = MagicMock(return_value=None)
        panel = ChatSettingsPanel(repository=repo, on_back=MagicMock())
        labels = [s["label"] for s in panel._settings]
        self.assertIn("META PROMPT", labels)

    def test_has_text_speed_setting(self):
        repo = MagicMock()
        repo.get_setting = MagicMock(return_value=None)
        panel = ChatSettingsPanel(repository=repo, on_back=MagicMock())
        labels = [s["label"] for s in panel._settings]
        self.assertIn("TEXT SPEED", labels)

    def test_has_voice_speed_setting(self):
        repo = MagicMock()
        repo.get_setting = MagicMock(return_value=None)
        panel = ChatSettingsPanel(repository=repo, on_back=MagicMock())
        labels = [s["label"] for s in panel._settings]
        self.assertIn("VOICE SPEED", labels)

    def test_short_press_cycles_settings(self):
        repo = MagicMock()
        repo.get_setting = MagicMock(return_value=None)
        panel = ChatSettingsPanel(repository=repo, on_back=MagicMock())
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._selected, 1)

    def test_long_press_calls_on_back(self):
        called = []
        repo = MagicMock()
        repo.get_setting = MagicMock(return_value=None)
        panel = ChatSettingsPanel(repository=repo, on_back=lambda: called.append(True))
        panel.handle_action("LONG_PRESS")
        self.assertTrue(called)


if __name__ == "__main__":
    unittest.main()
