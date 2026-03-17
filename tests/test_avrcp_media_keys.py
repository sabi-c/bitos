"""Tests for AVRCP / Bluetooth media key listener."""
import os
import sys
import threading
import time

import pytest

# Ensure device/ is on path
DEVICE_DIR = os.path.join(os.path.dirname(__file__), "..", "device")
if DEVICE_DIR not in sys.path:
    sys.path.insert(0, DEVICE_DIR)


class TestMediaKeyListener:
    """Test MediaKeyListener with mocked evdev."""

    def test_init_callbacks(self):
        from input.media_keys import MediaKeyListener, KEY_PLAYPAUSE, KEY_NEXTSONG, KEY_PREVIOUSSONG

        calls = []
        listener = MediaKeyListener(
            on_play_pause=lambda: calls.append("play_pause"),
            on_next=lambda: calls.append("next"),
            on_prev=lambda: calls.append("prev"),
        )
        assert KEY_PLAYPAUSE in listener._callbacks
        assert KEY_NEXTSONG in listener._callbacks
        assert KEY_PREVIOUSSONG in listener._callbacks

    def test_available_without_evdev(self, monkeypatch):
        from input import media_keys
        monkeypatch.setattr(media_keys, "_HAS_EVDEV", False)

        listener = media_keys.MediaKeyListener()
        assert listener.available is False
        assert listener.connected is False

    def test_start_without_evdev_is_noop(self, monkeypatch):
        from input import media_keys
        monkeypatch.setattr(media_keys, "_HAS_EVDEV", False)

        listener = media_keys.MediaKeyListener()
        listener.start()  # Should not raise
        assert listener._running is False

    def test_key_map_default(self):
        from input.media_keys import MediaKeyListener, MEDIA_KEY_MAP

        listener = MediaKeyListener()
        assert listener.key_map == MEDIA_KEY_MAP

    def test_key_map_override(self):
        from input.media_keys import MediaKeyListener

        custom = {"play_pause": "custom_action"}
        listener = MediaKeyListener(key_map=custom)
        assert listener.key_map == custom

    def test_stop_without_start(self):
        from input.media_keys import MediaKeyListener

        listener = MediaKeyListener()
        listener.stop()  # Should not raise

    def test_debounce_constants(self):
        """Verify debounce/scan constants are reasonable."""
        from input.media_keys import _DEVICE_SCAN_INTERVAL
        assert _DEVICE_SCAN_INTERVAL >= 1.0
        assert _DEVICE_SCAN_INTERVAL <= 30.0

    def test_find_bt_device_no_evdev(self, monkeypatch):
        from input import media_keys
        monkeypatch.setattr(media_keys, "_HAS_EVDEV", False)

        result = media_keys.MediaKeyListener._find_bt_input_device()
        assert result is None
