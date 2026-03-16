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

    def test_long_press_in_idle_does_not_exit(self):
        """LONG_PRESS should NOT call on_back anymore."""
        called = []
        panel = self._make_panel(on_back=lambda: called.append(True))
        panel.handle_action("LONG_PRESS")
        self.assertFalse(called)

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

    def test_short_press_in_field_recording_sends(self):
        panel = self._make_panel()
        panel._mode = ChatMode.RECORDING
        panel._quick_talk = False
        panel._voice_stop_event.clear()
        panel.handle_action("SHORT_PRESS")
        self.assertTrue(panel._voice_stop_event.is_set())
        self.assertFalse(panel._recording_cancelled)

    def test_short_press_in_quick_talk_ignored(self):
        panel = self._make_panel()
        panel._mode = ChatMode.RECORDING
        panel._quick_talk = True
        panel._voice_stop_event.clear()
        panel.handle_action("SHORT_PRESS")
        # SHORT_PRESS should not stop quick-talk — only HOLD_END does
        self.assertFalse(panel._voice_stop_event.is_set())

    def test_hold_end_stops_quick_talk(self):
        panel = self._make_panel()
        panel._mode = ChatMode.RECORDING
        panel._quick_talk = True
        panel._voice_stop_event.clear()
        panel.handle_action("HOLD_END")
        self.assertTrue(panel._voice_stop_event.is_set())

    def test_hold_end_does_not_stop_field_recording(self):
        panel = self._make_panel()
        panel._mode = ChatMode.RECORDING
        panel._quick_talk = False
        panel._voice_stop_event.clear()
        panel.handle_action("HOLD_END")
        # HOLD_END should not stop field recording — only SHORT_PRESS does
        self.assertFalse(panel._voice_stop_event.is_set())

    def test_short_press_in_idle_starts_field_recording(self):
        panel = self._make_panel()
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._mode, ChatMode.RECORDING)
        self.assertFalse(panel._quick_talk)

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

    def test_idle_action_bar_has_record_and_talk(self):
        panel = self._make_panel()
        content = panel._get_action_bar_content()
        self.assertEqual(len(content), 3)
        labels = [c[1] for c in content]
        self.assertIn("RECORD", labels)
        self.assertIn("TALK", labels)
        self.assertIn("ACTIONS", labels)

    def test_field_recording_action_bar(self):
        panel = self._make_panel()
        panel._mode = ChatMode.RECORDING
        panel._quick_talk = False
        content = panel._get_action_bar_content()
        self.assertEqual(len(content), 2)
        labels = [c[1] for c in content]
        self.assertIn("STOP & SEND", labels)
        self.assertIn("CANCEL", labels)

    def test_quick_talk_action_bar(self):
        panel = self._make_panel()
        panel._mode = ChatMode.RECORDING
        panel._quick_talk = True
        content = panel._get_action_bar_content()
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0][1], "RELEASE TO SEND")

    def test_streaming_action_bar_empty(self):
        panel = self._make_panel()
        panel._mode = ChatMode.STREAMING
        content = panel._get_action_bar_content()
        self.assertEqual(len(content), 0)

    def test_selecting_back_to_main_menu_calls_on_back(self):
        called = []
        panel = self._make_panel(on_back=lambda: called.append(True))
        panel._mode = ChatMode.ACTIONS
        # Navigate to BACK TO MAIN MENU (last item in actions)
        panel._action_template_index = len(panel._action_items()) - 1
        panel.handle_action("DOUBLE_PRESS")
        self.assertTrue(called)
        self.assertEqual(panel._mode, ChatMode.IDLE)

    def test_split_into_pages_single_page(self):
        panel = self._make_panel()
        lines = ["line one", "line two", "line three"]
        pages = panel._split_into_pages(lines, lines_per_page=9)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0], lines)

    def test_split_into_pages_multiple(self):
        panel = self._make_panel()
        lines = [f"line {i}" for i in range(20)]
        pages = panel._split_into_pages(lines, lines_per_page=9)
        self.assertEqual(len(pages), 3)
        self.assertEqual(len(pages[0]), 9)
        self.assertEqual(len(pages[1]), 9)
        self.assertEqual(len(pages[2]), 2)

    def test_split_into_pages_max_four(self):
        panel = self._make_panel()
        lines = [f"line {i}" for i in range(50)]
        pages = panel._split_into_pages(lines, lines_per_page=9)
        self.assertEqual(len(pages), 4)
        # Last line of page 4 should end with "..."
        self.assertTrue(pages[3][-1].endswith("..."))

    def test_split_into_pages_paragraph_boundary(self):
        panel = self._make_panel()
        # Lines with a paragraph break (empty line) near page boundary
        lines = [f"line {i}" for i in range(7)] + [""] + [f"para2 line {i}" for i in range(5)]
        pages = panel._split_into_pages(lines, lines_per_page=9)
        # Should split at the paragraph break (after empty line at index 7)
        self.assertEqual(len(pages), 2)
        self.assertEqual(pages[0][-1], "")  # empty line at end of page 1


    def test_triple_press_advances_page(self):
        panel = self._make_panel()
        panel._pages = [["page1 line"], ["page2 line"], ["page3 line"]]
        panel._page_revealed = [True, False, False]
        panel._current_page = 0
        panel.handle_action("TRIPLE_PRESS")
        self.assertEqual(panel._current_page, 1)

    def test_triple_press_cycles_around(self):
        panel = self._make_panel()
        panel._pages = [["p1"], ["p2"]]
        panel._page_revealed = [True, True]
        panel._current_page = 1
        panel.handle_action("TRIPLE_PRESS")
        self.assertEqual(panel._current_page, 0)

    def test_triple_press_reveals_current_page(self):
        panel = self._make_panel()
        panel._pages = [["p1 line1", "p1 line2"], ["p2"]]
        panel._page_revealed = [False, False]
        panel._current_page = 0
        panel._page_typewriter = MagicMock()
        panel._page_typewriter.finished = False
        panel.handle_action("TRIPLE_PRESS")
        self.assertTrue(panel._page_revealed[0])
        self.assertEqual(panel._current_page, 1)

    def test_no_triple_press_without_pages(self):
        panel = self._make_panel()
        panel._pages = []
        panel._current_page = 0
        panel.handle_action("TRIPLE_PRESS")
        self.assertEqual(panel._current_page, 0)

    def test_page_typewriter_created_on_first_view(self):
        panel = self._make_panel()
        panel._pages = [["hello world", "second line"]]
        panel._page_revealed = [False]
        panel._current_page = 0
        panel._start_page_typewriter()
        self.assertIsNotNone(panel._page_typewriter)

    def test_page_typewriter_skipped_on_revisit(self):
        panel = self._make_panel()
        panel._pages = [["hello world"]]
        panel._page_revealed = [True]
        panel._current_page = 0
        panel._start_page_typewriter()
        self.assertIsNone(panel._page_typewriter)


    def test_build_pages_from_response(self):
        panel = self._make_panel()
        panel._context_header = ""
        panel._build_pages("hello world. this is a test response.")
        self.assertGreaterEqual(len(panel._pages), 1)
        self.assertEqual(panel._current_page, 0)
        self.assertEqual(len(panel._page_revealed), len(panel._pages))
        self.assertFalse(panel._page_revealed[0])

    def test_build_pages_sets_context_header(self):
        panel = self._make_panel()
        panel._build_pages("response text", user_message="what should I focus on today?")
        self.assertTrue(panel._context_header.startswith("> "))
        self.assertLessEqual(len(panel._context_header), 42)  # "> " + 35 chars + "..."

    def test_build_pages_truncates_long_user_message(self):
        panel = self._make_panel()
        long_msg = "a" * 50
        panel._build_pages("response", user_message=long_msg)
        self.assertTrue(panel._context_header.endswith("..."))
        self.assertLessEqual(len(panel._context_header), 42)


if __name__ == "__main__":
    unittest.main()
