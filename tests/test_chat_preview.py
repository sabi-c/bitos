"""Tests for ChatPreviewPanel greeting + response field + inline recording."""
import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from device.ui.panels.chat_preview import ChatPreviewPanel, CHAT_ITEMS, RecState


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

    def test_respond_action_fires_callback_when_ready(self):
        """In READY state, DOUBLE on non-RECORD items fires normal callback."""
        cb = MagicMock()
        panel = ChatPreviewPanel(on_action=cb)
        panel.selected_index = 1  # START NEW CHAT
        panel.handle_action("DOUBLE_PRESS")
        cb.assert_called_once_with("new_chat")

    def test_starts_with_no_highlight(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        self.assertEqual(panel.selected_index, -1)

    def test_item_count(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        self.assertEqual(len(panel.items), 6)

    def test_items_are_deep_copied(self):
        panel_a = ChatPreviewPanel(on_action=MagicMock())
        panel_a.set_resume_info("chat A", "1h ago")
        panel_b = ChatPreviewPanel(on_action=MagicMock())
        resume_b = next(i for i in panel_b.items if i["action"] == "resume_chat")
        self.assertEqual(resume_b.get("subtext", ""), "")

    def test_greeting_truncated_to_max(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        long_text = "x" * 200
        panel.set_greeting(long_text)
        self.assertEqual(len(panel._greeting_text), 60)

    # ── Dynamic greeting height ──

    def test_greeting_height_min(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        self.assertEqual(panel._measured_greeting_h, 40)

    def test_greeting_height_grows_with_text(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        panel.set_greeting("Hello there, good morning to you")
        self.assertGreaterEqual(panel._measured_greeting_h, 40)

    def test_greeting_height_capped(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        panel._measured_greeting_h = 200
        panel.set_greeting("x " * 30)
        self.assertLessEqual(panel._measured_greeting_h, 200)  # set_greeting doesn't render

    # ── RecState ──

    def test_initial_rec_state_is_ready(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        self.assertEqual(panel._rec_state, RecState.READY)

    def test_double_press_on_record_starts_recording(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        panel.selected_index = 0
        panel.handle_action("DOUBLE_PRESS")
        self.assertEqual(panel._rec_state, RecState.RECORDING)

    def test_short_press_during_recording_stops(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        panel._rec_state = RecState.RECORDING
        panel.handle_action("SHORT_PRESS")
        self.assertNotEqual(panel._rec_state, RecState.RECORDING)

    def test_long_press_during_recording_cancels(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        panel._start_inline_recording()
        panel._cancel_inline_recording()
        self.assertEqual(panel._rec_state, RecState.READY)

    def test_gestures_ignored_during_transcribing(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        panel._rec_state = RecState.TRANSCRIBING
        panel.selected_index = 0
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel.selected_index, 0)
        self.assertEqual(panel._rec_state, RecState.TRANSCRIBING)

    def test_short_press_on_error_retries(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        panel._rec_state = RecState.ERROR
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel._rec_state, RecState.RECORDING)

    def test_normal_items_still_work_in_ready(self):
        cb = MagicMock()
        panel = ChatPreviewPanel(on_action=cb)
        panel.selected_index = 1
        panel.handle_action("DOUBLE_PRESS")
        cb.assert_called_once_with("new_chat")

    # ── Expansion animation ──

    def test_launching_animation_advances(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        panel._rec_state = RecState.LAUNCHING
        panel._launch_anim_frame = 0
        panel._transcribed_text = "hello"
        panel.update(1 / 15)
        self.assertEqual(panel._launch_anim_frame, 1)
        self.assertGreater(panel._launch_current_h, 22)

    def test_launching_triggers_handoff(self):
        cb = MagicMock()
        panel = ChatPreviewPanel(on_action=cb)
        panel._rec_state = RecState.LAUNCHING
        panel._transcribed_text = "test message"
        for _ in range(10):
            panel.update(1 / 15)
        cb.assert_called_with("respond_with_text")

    # ── Integration ──

    def test_full_recording_flow(self):
        cb = MagicMock()
        mock_pipeline = MagicMock()
        mock_pipeline.stop_and_process.return_value = MagicMock(path="/tmp/test.wav")

        def mock_stt(path):
            return "hello world"

        panel = ChatPreviewPanel(
            on_action=cb,
            audio_pipeline=mock_pipeline,
            stt_callable=mock_stt,
        )
        panel.selected_index = 0

        # Start recording
        panel.handle_action("DOUBLE_PRESS")
        self.assertEqual(panel._rec_state, RecState.RECORDING)
        mock_pipeline.start_recording.assert_called_once()

        # Stop recording — STT runs in background thread
        panel.handle_action("SHORT_PRESS")
        time.sleep(0.3)
        self.assertEqual(panel._rec_state, RecState.LAUNCHING)
        self.assertEqual(panel._transcribed_text, "hello world")

        # Advance animation to completion
        for _ in range(10):
            panel.update(1 / 15)
        cb.assert_called_with("respond_with_text")

    def test_record_item_has_subtext(self):
        panel = ChatPreviewPanel(on_action=MagicMock())
        record_item = panel.items[0]
        self.assertEqual(record_item.get("subtext"), "Double-click to record")


if __name__ == "__main__":
    unittest.main()
