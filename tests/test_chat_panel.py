"""Tests for ChatPanel gesture-driven input modes."""
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from screens.panels.chat import ChatPanel, ChatMode


class ChatModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _make_panel(self, **kwargs):
        client = MagicMock()
        client.chat = MagicMock(return_value=iter(["hello"]))
        repo = MagicMock()
        repo.get_setting = MagicMock(return_value=None)
        repo.get_latest_session = MagicMock(return_value=None)
        audio = kwargs.get("audio", MagicMock())
        audio.is_speaking = MagicMock(return_value=False)
        audio.is_available = MagicMock(return_value=True)
        return ChatPanel(
            client=client,
            repository=repo,
            on_back=kwargs.get("on_back"),
            audio_pipeline=audio,
        )

    def test_starts_in_idle_mode(self):
        panel = self._make_panel()
        self.assertEqual(panel._mode, ChatMode.IDLE)

    def test_long_press_in_idle_exits_chat(self):
        called = []
        panel = self._make_panel(on_back=lambda: called.append(True))
        panel.handle_action("LONG_PRESS")
        self.assertTrue(called)

    def test_long_press_during_hold_does_not_exit(self):
        called = []
        panel = self._make_panel(on_back=lambda: called.append(True))
        panel.handle_action("HOLD_START")  # Sets hold timer
        panel.handle_action("LONG_PRESS")  # Should be ignored (hold in progress)
        self.assertFalse(called)

    def test_double_press_in_idle_opens_actions(self):
        panel = self._make_panel()
        panel.handle_action("DOUBLE_PRESS")
        self.assertEqual(panel._mode, ChatMode.ACTIONS)

    def test_short_press_in_actions_cycles(self):
        panel = self._make_panel()
        panel._mode = ChatMode.ACTIONS
        panel._action_template_index = 0
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._action_template_index, 1)

    def test_long_press_in_actions_returns_to_idle(self):
        panel = self._make_panel()
        panel._mode = ChatMode.ACTIONS
        panel.handle_action("LONG_PRESS")
        self.assertEqual(panel._mode, ChatMode.IDLE)

    def test_long_press_in_recording_cancels(self):
        panel = self._make_panel()
        panel._mode = ChatMode.RECORDING
        panel._voice_stop_event.clear()
        panel.handle_action("LONG_PRESS")
        self.assertTrue(panel._recording_cancelled)
        self.assertTrue(panel._voice_stop_event.is_set())

    def test_short_press_in_recording_sends(self):
        panel = self._make_panel()
        panel._mode = ChatMode.RECORDING
        panel._voice_stop_event.clear()
        panel.handle_action("SHORT_PRESS")
        self.assertTrue(panel._voice_stop_event.is_set())
        self.assertFalse(panel._recording_cancelled)

    def test_short_press_in_idle_scrolls(self):
        panel = self._make_panel()
        panel._scroll_offset = 5
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._scroll_offset, 4)

    def test_speaking_mode_any_press_stops(self):
        audio = MagicMock()
        audio.is_speaking = MagicMock(return_value=True)
        audio.is_available = MagicMock(return_value=True)
        panel = self._make_panel(audio=audio)
        panel._mode = ChatMode.SPEAKING
        panel.handle_action("SHORT_PRESS")
        audio.stop_speaking.assert_called_once()
        self.assertEqual(panel._mode, ChatMode.IDLE)

    def test_streaming_ignores_input(self):
        panel = self._make_panel()
        panel._mode = ChatMode.STREAMING
        panel._scroll_offset = 5
        panel.handle_action("SHORT_PRESS")
        # Should not change anything
        self.assertEqual(panel._scroll_offset, 5)
        self.assertEqual(panel._mode, ChatMode.STREAMING)

    def test_hold_start_sets_timer(self):
        panel = self._make_panel()
        panel.handle_action("HOLD_START")
        self.assertIsNotNone(panel._hold_timer)

    def test_hold_end_clears_timer(self):
        panel = self._make_panel()
        panel._hold_timer = 12345.0
        panel.handle_action("HOLD_END")
        self.assertIsNone(panel._hold_timer)

    def test_idle_action_bar_has_record(self):
        panel = self._make_panel()
        content = panel._get_action_bar_content()
        self.assertEqual(len(content), 3)
        icons = [c[0] for c in content]
        self.assertIn("hold", icons)
        labels = [c[1] for c in content]
        self.assertIn("RECORD", labels)

    def test_recording_action_bar_has_release_send(self):
        panel = self._make_panel()
        panel._mode = ChatMode.RECORDING
        content = panel._get_action_bar_content()
        self.assertEqual(len(content), 2)
        labels = [c[1] for c in content]
        self.assertIn("RELEASE", labels)
        self.assertIn("SEND", labels)

    def test_streaming_action_bar_empty(self):
        panel = self._make_panel()
        panel._mode = ChatMode.STREAMING
        content = panel._get_action_bar_content()
        self.assertEqual(len(content), 0)


if __name__ == "__main__":
    unittest.main()
