"""Tests for AVRCP media key listener."""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))


class TestMediaKeyConstants(unittest.TestCase):
    """Tests for key code constants."""

    def test_key_constants(self):
        from input.media_keys import KEY_PLAYPAUSE, KEY_NEXTSONG, KEY_PREVIOUSSONG
        self.assertEqual(KEY_PLAYPAUSE, 164)
        self.assertEqual(KEY_NEXTSONG, 163)
        self.assertEqual(KEY_PREVIOUSSONG, 165)


class TestMediaKeyListenerInit(unittest.TestCase):
    """Tests for MediaKeyListener initialization."""

    def test_default_state(self):
        from input.media_keys import MediaKeyListener
        listener = MediaKeyListener()
        self.assertFalse(listener.connected)
        self.assertIsNotNone(listener.key_map)

    def test_with_callbacks(self):
        from input.media_keys import MediaKeyListener
        cb = MagicMock()
        listener = MediaKeyListener(on_play_pause=cb, on_next=cb, on_prev=cb)
        self.assertEqual(len(listener._callbacks), 3)

    @patch("input.media_keys._HAS_EVDEV", False)
    def test_not_available_without_evdev(self):
        from input.media_keys import MediaKeyListener
        listener = MediaKeyListener()
        self.assertFalse(listener.available)

    @patch("input.media_keys._HAS_EVDEV", False)
    def test_start_without_evdev(self):
        from input.media_keys import MediaKeyListener
        listener = MediaKeyListener()
        listener.start()  # Should not crash, just log
        self.assertFalse(listener.connected)

    def test_stop_without_start(self):
        from input.media_keys import MediaKeyListener
        listener = MediaKeyListener()
        listener.stop()  # Should not crash

    def test_key_map_is_copy(self):
        from input.media_keys import MediaKeyListener
        listener = MediaKeyListener()
        m = listener.key_map
        m["test"] = "value"
        self.assertNotIn("test", listener.key_map)


if __name__ == "__main__":
    unittest.main()
