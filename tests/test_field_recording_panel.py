"""Tests for FieldRecordingPanel — state machine, rendering, store integration."""
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from device.ui.panels.field_recording_panel import (
    FieldRecordingPanel, FieldRecState, _format_duration, _format_time_ago,
)
from device.recordings import RecordingStore


class FieldRecordingPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _make_panel(self, **kwargs):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "recordings.json")
        store = RecordingStore(path=path)
        self._cleanup_paths = getattr(self, "_cleanup_paths", [])
        self._cleanup_paths.append((path, tmpdir))
        return FieldRecordingPanel(
            on_action=kwargs.get("on_action", MagicMock()),
            recording_store=store,
        )

    def tearDown(self):
        for path, tmpdir in getattr(self, "_cleanup_paths", []):
            if os.path.exists(path):
                os.remove(path)
            if os.path.exists(tmpdir):
                os.rmdir(tmpdir)

    # ── Initial state ──

    def test_initial_state_is_idle(self):
        panel = self._make_panel()
        self.assertEqual(panel.state, FieldRecState.IDLE)

    def test_initial_items_include_new_recording_and_back(self):
        panel = self._make_panel()
        self.assertEqual(panel.items[0]["action"], "new_recording")
        self.assertEqual(panel.items[-1]["action"], "back")

    def test_starts_with_no_highlight(self):
        panel = self._make_panel()
        self.assertEqual(panel.selected_index, -1)

    # ── State transitions ──

    def test_double_press_on_new_recording_starts_recording(self):
        panel = self._make_panel()
        panel.selected_index = 0
        panel.handle_action("DOUBLE_PRESS")
        self.assertEqual(panel.state, FieldRecState.RECORDING)

    def test_short_press_during_recording_stops(self):
        panel = self._make_panel()
        panel._start_recording()
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel.state, FieldRecState.DONE)

    def test_double_press_during_recording_stops(self):
        panel = self._make_panel()
        panel._start_recording()
        panel.handle_action("DOUBLE_PRESS")
        self.assertEqual(panel.state, FieldRecState.DONE)

    def test_long_press_during_recording_cancels(self):
        panel = self._make_panel()
        panel._start_recording()
        panel.handle_action("LONG_PRESS")
        self.assertEqual(panel.state, FieldRecState.IDLE)

    def test_any_press_during_done_returns_to_idle(self):
        panel = self._make_panel()
        panel._state = FieldRecState.DONE
        panel._done_time = time.time()
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel.state, FieldRecState.IDLE)

    def test_input_swallowed_during_saving(self):
        panel = self._make_panel()
        panel._state = FieldRecState.SAVING
        result = panel.handle_action("SHORT_PRESS")
        self.assertTrue(result)
        self.assertEqual(panel.state, FieldRecState.SAVING)

    # ── Recording creates store entry ──

    def test_stop_saves_recording_metadata(self):
        panel = self._make_panel()
        panel._start_recording()
        time.sleep(0.05)  # tiny duration
        panel._stop_recording()
        self.assertIsNotNone(panel._saved_recording)
        self.assertGreater(panel._saved_recording.duration_s, 0)
        self.assertEqual(panel._store.count(), 1)

    def test_cancel_does_not_save(self):
        panel = self._make_panel()
        panel._start_recording()
        panel._cancel_recording()
        self.assertEqual(panel._store.count(), 0)

    # ── Recent recordings appear in items ──

    def test_recent_recordings_appear_in_menu(self):
        panel = self._make_panel()
        panel._store.create(duration_s=30.0)
        panel._store.create(duration_s=60.0)
        panel._refresh_items()
        # NEW RECORDING + 2 recordings + BACK
        self.assertEqual(len(panel.items), 4)
        self.assertIn("recording", panel.items[1]["label"])

    # ── Elapsed timer ──

    def test_elapsed_returns_zero_when_idle(self):
        panel = self._make_panel()
        self.assertEqual(panel.elapsed, 0.0)

    def test_elapsed_positive_when_recording(self):
        panel = self._make_panel()
        panel._start_recording()
        time.sleep(0.02)
        self.assertGreater(panel.elapsed, 0)

    # ── Auto-dismiss DONE ──

    def test_done_auto_dismisses_after_timeout(self):
        panel = self._make_panel()
        panel._state = FieldRecState.DONE
        panel._done_time = time.time() - 3.0  # 3s ago, > 2s threshold
        panel.update(0.1)
        self.assertEqual(panel.state, FieldRecState.IDLE)

    def test_done_stays_within_timeout(self):
        panel = self._make_panel()
        panel._state = FieldRecState.DONE
        panel._done_time = time.time()  # just now
        panel.update(0.1)
        self.assertEqual(panel.state, FieldRecState.DONE)

    # ── Normal navigation in IDLE ──

    def test_short_press_cycles_items(self):
        panel = self._make_panel()
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel.selected_index, 0)
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel.selected_index, 1)

    def test_double_press_on_back_fires_callback(self):
        cb = MagicMock()
        panel = self._make_panel(on_action=cb)
        panel.selected_index = len(panel.items) - 1  # BACK
        panel.handle_action("DOUBLE_PRESS")
        cb.assert_called_once_with("back")

    # ── Render smoke tests ──

    def test_render_idle_no_crash(self):
        panel = self._make_panel()
        surface = pygame.Surface((156, 208))
        panel.render(surface)

    def test_render_recording_no_crash(self):
        panel = self._make_panel()
        panel._start_recording()
        surface = pygame.Surface((156, 208))
        panel.render(surface)

    def test_render_saving_no_crash(self):
        panel = self._make_panel()
        panel._state = FieldRecState.SAVING
        surface = pygame.Surface((156, 208))
        panel.render(surface)

    def test_render_done_no_crash(self):
        panel = self._make_panel()
        panel._state = FieldRecState.DONE
        panel._saved_recording = panel._store.create(duration_s=10.0)
        surface = pygame.Surface((156, 208))
        panel.render(surface)

    # ── Full flow ──

    def test_full_recording_flow(self):
        cb = MagicMock()
        panel = self._make_panel(on_action=cb)

        # Navigate to NEW RECORDING
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel.selected_index, 0)

        # Start recording
        panel.handle_action("DOUBLE_PRESS")
        self.assertEqual(panel.state, FieldRecState.RECORDING)

        # Wait a bit, then stop
        time.sleep(0.02)
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel.state, FieldRecState.DONE)
        self.assertEqual(panel._store.count(), 1)

        # Dismiss
        panel.handle_action("SHORT_PRESS")
        self.assertEqual(panel.state, FieldRecState.IDLE)

        # Recording now in menu
        self.assertGreater(len(panel.items), 2)


class FormatHelperTests(unittest.TestCase):
    def test_format_duration(self):
        self.assertEqual(_format_duration(0), "0:00")
        self.assertEqual(_format_duration(65), "1:05")
        self.assertEqual(_format_duration(3661), "61:01")

    def test_format_time_ago_just_now(self):
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        self.assertEqual(_format_time_ago(now), "just now")

    def test_format_time_ago_bad_input(self):
        self.assertEqual(_format_time_ago("not-a-date"), "")


if __name__ == "__main__":
    unittest.main()
