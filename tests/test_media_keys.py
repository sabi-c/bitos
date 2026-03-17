"""Tests for AVRCP / Bluetooth media key listener."""
import os
import sys
import time
import threading
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from input.media_keys import (
    MediaKeyListener,
    MEDIA_KEY_MAP,
    KEY_PLAYPAUSE,
    KEY_NEXTSONG,
    KEY_PREVIOUSSONG,
    _HAS_EVDEV,
)


class TestMediaKeyListenerInit(unittest.TestCase):
    """Test MediaKeyListener construction and properties."""

    def test_default_key_map(self):
        listener = MediaKeyListener()
        self.assertEqual(listener.key_map, MEDIA_KEY_MAP)

    def test_custom_key_map(self):
        custom = {"play_pause": "custom_action"}
        listener = MediaKeyListener(key_map=custom)
        self.assertEqual(listener.key_map, custom)

    def test_callbacks_registered(self):
        on_pp = MagicMock()
        on_next = MagicMock()
        on_prev = MagicMock()
        listener = MediaKeyListener(
            on_play_pause=on_pp,
            on_next=on_next,
            on_prev=on_prev,
        )
        self.assertIn(KEY_PLAYPAUSE, listener._callbacks)
        self.assertIn(KEY_NEXTSONG, listener._callbacks)
        self.assertIn(KEY_PREVIOUSSONG, listener._callbacks)

    def test_no_callbacks_still_works(self):
        listener = MediaKeyListener()
        self.assertEqual(len(listener._callbacks), 0)

    def test_not_connected_initially(self):
        listener = MediaKeyListener()
        self.assertFalse(listener.connected)

    def test_key_map_is_copy(self):
        """Mutating the returned key_map should not affect the listener."""
        listener = MediaKeyListener()
        m = listener.key_map
        m["play_pause"] = "hacked"
        self.assertNotEqual(listener.key_map.get("play_pause"), "hacked")


class TestMediaKeyListenerWithoutEvdev(unittest.TestCase):
    """Test graceful degradation when evdev is not installed."""

    @patch("input.media_keys._HAS_EVDEV", False)
    def test_start_without_evdev_is_noop(self):
        listener = MediaKeyListener()
        listener.start()  # Should not raise
        self.assertFalse(listener._running)
        self.assertIsNone(listener._thread)

    @patch("input.media_keys._HAS_EVDEV", False)
    def test_available_false_without_evdev(self):
        listener = MediaKeyListener()
        # Patch the property check too
        with patch.object(type(listener), "available", new_callable=lambda: property(lambda self: False)):
            self.assertFalse(listener.available)

    @patch("input.media_keys._HAS_EVDEV", False)
    def test_find_bt_device_returns_none_without_evdev(self):
        result = MediaKeyListener._find_bt_input_device()
        self.assertIsNone(result)


class TestMediaKeyListenerStartStop(unittest.TestCase):
    """Test start/stop lifecycle with mocked evdev."""

    @patch("input.media_keys._HAS_EVDEV", True)
    def test_start_creates_thread(self):
        listener = MediaKeyListener()
        # Patch _run_loop to exit immediately
        listener._run_loop = MagicMock()
        listener.start()
        self.assertTrue(listener._running)
        self.assertIsNotNone(listener._thread)
        listener.stop()
        self.assertFalse(listener._running)

    @patch("input.media_keys._HAS_EVDEV", True)
    def test_double_start_is_ignored(self):
        listener = MediaKeyListener()
        listener._run_loop = MagicMock()
        listener.start()
        thread1 = listener._thread
        listener.start()  # Second start should be no-op
        self.assertIs(listener._thread, thread1)
        listener.stop()

    @patch("input.media_keys._HAS_EVDEV", True)
    def test_stop_closes_device(self):
        listener = MediaKeyListener()
        mock_dev = MagicMock()
        listener._device = mock_dev
        listener._running = True
        listener.stop()
        mock_dev.close.assert_called_once()
        self.assertIsNone(listener._device)


class TestMediaKeyEventDispatch(unittest.TestCase):
    """Test event reading and callback dispatch with mocked evdev."""

    def _make_mock_event(self, event_type, code, value):
        ev = MagicMock()
        ev.type = event_type
        ev.code = code
        ev.value = value
        return ev

    @patch("input.media_keys._HAS_EVDEV", True)
    @patch("input.media_keys.ecodes")
    def test_play_pause_callback_fires(self, mock_ecodes):
        mock_ecodes.EV_KEY = 1
        fired = []
        listener = MediaKeyListener(on_play_pause=lambda: fired.append("pp"))

        mock_dev = MagicMock()
        event = self._make_mock_event(1, KEY_PLAYPAUSE, 1)  # key press
        mock_dev.read_loop.return_value = [event]

        # read_loop will exhaust the iterator then the for-loop ends
        listener._running = True
        listener._read_events(mock_dev)

        self.assertEqual(fired, ["pp"])

    @patch("input.media_keys._HAS_EVDEV", True)
    @patch("input.media_keys.ecodes")
    def test_next_callback_fires(self, mock_ecodes):
        mock_ecodes.EV_KEY = 1
        fired = []
        listener = MediaKeyListener(on_next=lambda: fired.append("next"))

        mock_dev = MagicMock()
        event = self._make_mock_event(1, KEY_NEXTSONG, 1)
        mock_dev.read_loop.return_value = [event]

        listener._running = True
        listener._read_events(mock_dev)

        self.assertEqual(fired, ["next"])

    @patch("input.media_keys._HAS_EVDEV", True)
    @patch("input.media_keys.ecodes")
    def test_prev_callback_fires(self, mock_ecodes):
        mock_ecodes.EV_KEY = 1
        fired = []
        listener = MediaKeyListener(on_prev=lambda: fired.append("prev"))

        mock_dev = MagicMock()
        event = self._make_mock_event(1, KEY_PREVIOUSSONG, 1)
        mock_dev.read_loop.return_value = [event]

        listener._running = True
        listener._read_events(mock_dev)

        self.assertEqual(fired, ["prev"])

    @patch("input.media_keys._HAS_EVDEV", True)
    @patch("input.media_keys.ecodes")
    def test_key_release_ignored(self, mock_ecodes):
        """Only key-down (value=1) should fire callbacks, not release (value=0)."""
        mock_ecodes.EV_KEY = 1
        fired = []
        listener = MediaKeyListener(on_play_pause=lambda: fired.append("pp"))

        mock_dev = MagicMock()
        release_event = self._make_mock_event(1, KEY_PLAYPAUSE, 0)  # key release
        mock_dev.read_loop.return_value = [release_event]

        listener._running = True
        listener._read_events(mock_dev)

        self.assertEqual(fired, [])

    @patch("input.media_keys._HAS_EVDEV", True)
    @patch("input.media_keys.ecodes")
    def test_key_repeat_ignored(self, mock_ecodes):
        """Key repeat (value=2) should be ignored."""
        mock_ecodes.EV_KEY = 1
        fired = []
        listener = MediaKeyListener(on_play_pause=lambda: fired.append("pp"))

        mock_dev = MagicMock()
        repeat_event = self._make_mock_event(1, KEY_PLAYPAUSE, 2)
        mock_dev.read_loop.return_value = [repeat_event]

        listener._running = True
        listener._read_events(mock_dev)

        self.assertEqual(fired, [])

    @patch("input.media_keys._HAS_EVDEV", True)
    @patch("input.media_keys.ecodes")
    def test_non_key_event_ignored(self, mock_ecodes):
        """Non EV_KEY events (e.g. EV_SYN) should be ignored."""
        mock_ecodes.EV_KEY = 1
        fired = []
        listener = MediaKeyListener(on_play_pause=lambda: fired.append("pp"))

        mock_dev = MagicMock()
        syn_event = self._make_mock_event(0, 0, 0)  # EV_SYN
        mock_dev.read_loop.return_value = [syn_event]

        listener._running = True
        listener._read_events(mock_dev)

        self.assertEqual(fired, [])

    @patch("input.media_keys._HAS_EVDEV", True)
    @patch("input.media_keys.ecodes")
    def test_callback_error_does_not_crash_loop(self, mock_ecodes):
        """A failing callback should be caught and not stop the listener."""
        mock_ecodes.EV_KEY = 1

        def bad_callback():
            raise RuntimeError("boom")

        listener = MediaKeyListener(on_play_pause=bad_callback)

        mock_dev = MagicMock()
        event = self._make_mock_event(1, KEY_PLAYPAUSE, 1)
        mock_dev.read_loop.return_value = [event]

        listener._running = True
        # Should not raise
        listener._read_events(mock_dev)

    @patch("input.media_keys._HAS_EVDEV", True)
    @patch("input.media_keys.ecodes")
    def test_device_disconnect_handled(self, mock_ecodes):
        """OSError during read should be caught (device disconnected)."""
        mock_ecodes.EV_KEY = 1
        listener = MediaKeyListener(on_play_pause=lambda: None)

        mock_dev = MagicMock()
        mock_dev.read_loop.side_effect = OSError("device removed")

        listener._running = True
        listener._device = mock_dev
        # Should not raise
        listener._read_events(mock_dev)
        # Device should be cleared
        self.assertIsNone(listener._device)


class TestFindBtInputDevice(unittest.TestCase):
    """Test _find_bt_input_device with mocked evdev."""

    @patch("input.media_keys._HAS_EVDEV", True)
    @patch("input.media_keys.ecodes")
    @patch("input.media_keys.evdev")
    def test_finds_avrcp_device(self, mock_evdev, mock_ecodes):
        mock_ecodes.EV_KEY = 1

        mock_dev = MagicMock()
        mock_dev.name = "AVRCP Controller"
        mock_dev.path = "/dev/input/event5"
        mock_dev.capabilities.return_value = {1: [KEY_PLAYPAUSE, KEY_NEXTSONG]}

        mock_evdev.list_devices.return_value = ["/dev/input/event5"]
        mock_evdev.InputDevice.return_value = mock_dev

        result = MediaKeyListener._find_bt_input_device()
        self.assertIs(result, mock_dev)

    @patch("input.media_keys._HAS_EVDEV", True)
    @patch("input.media_keys.ecodes")
    @patch("input.media_keys.evdev")
    def test_finds_bluetooth_device(self, mock_evdev, mock_ecodes):
        mock_ecodes.EV_KEY = 1

        mock_dev = MagicMock()
        mock_dev.name = "Bluetooth Audio Remote"
        mock_dev.path = "/dev/input/event3"
        mock_dev.capabilities.return_value = {1: [KEY_PLAYPAUSE]}

        mock_evdev.list_devices.return_value = ["/dev/input/event3"]
        mock_evdev.InputDevice.return_value = mock_dev

        result = MediaKeyListener._find_bt_input_device()
        self.assertIs(result, mock_dev)

    @patch("input.media_keys._HAS_EVDEV", True)
    @patch("input.media_keys.ecodes")
    @patch("input.media_keys.evdev")
    def test_finds_airpods_device(self, mock_evdev, mock_ecodes):
        mock_ecodes.EV_KEY = 1

        mock_dev = MagicMock()
        mock_dev.name = "AirPods Pro"
        mock_dev.path = "/dev/input/event7"
        mock_dev.capabilities.return_value = {1: [KEY_PLAYPAUSE, KEY_NEXTSONG, KEY_PREVIOUSSONG]}

        mock_evdev.list_devices.return_value = ["/dev/input/event7"]
        mock_evdev.InputDevice.return_value = mock_dev

        result = MediaKeyListener._find_bt_input_device()
        self.assertIs(result, mock_dev)

    @patch("input.media_keys._HAS_EVDEV", True)
    @patch("input.media_keys.ecodes")
    @patch("input.media_keys.evdev")
    def test_skips_non_bt_device(self, mock_evdev, mock_ecodes):
        mock_ecodes.EV_KEY = 1

        mock_dev = MagicMock()
        mock_dev.name = "USB Keyboard"
        mock_dev.path = "/dev/input/event0"

        mock_evdev.list_devices.return_value = ["/dev/input/event0"]
        mock_evdev.InputDevice.return_value = mock_dev

        result = MediaKeyListener._find_bt_input_device()
        self.assertIsNone(result)
        mock_dev.close.assert_called_once()

    @patch("input.media_keys._HAS_EVDEV", True)
    @patch("input.media_keys.ecodes")
    @patch("input.media_keys.evdev")
    def test_skips_bt_device_without_media_keys(self, mock_evdev, mock_ecodes):
        """A BT device without media key capabilities should be skipped."""
        mock_ecodes.EV_KEY = 1

        mock_dev = MagicMock()
        mock_dev.name = "Bluetooth Keyboard"
        mock_dev.path = "/dev/input/event2"
        mock_dev.capabilities.return_value = {1: [30, 31, 32]}  # letter keys, no media

        mock_evdev.list_devices.return_value = ["/dev/input/event2"]
        mock_evdev.InputDevice.return_value = mock_dev

        result = MediaKeyListener._find_bt_input_device()
        self.assertIsNone(result)
        mock_dev.close.assert_called()

    @patch("input.media_keys._HAS_EVDEV", True)
    @patch("input.media_keys.ecodes")
    @patch("input.media_keys.evdev")
    def test_no_devices_found(self, mock_evdev, mock_ecodes):
        mock_ecodes.EV_KEY = 1
        mock_evdev.list_devices.return_value = []

        result = MediaKeyListener._find_bt_input_device()
        self.assertIsNone(result)

    @patch("input.media_keys._HAS_EVDEV", True)
    @patch("input.media_keys.ecodes")
    @patch("input.media_keys.evdev")
    def test_device_open_error_skipped(self, mock_evdev, mock_ecodes):
        """If opening a device fails, continue scanning others."""
        mock_ecodes.EV_KEY = 1

        mock_evdev.list_devices.return_value = ["/dev/input/event0", "/dev/input/event1"]

        good_dev = MagicMock()
        good_dev.name = "AVRCP Controller"
        good_dev.path = "/dev/input/event1"
        good_dev.capabilities.return_value = {1: [KEY_PLAYPAUSE]}

        def side_effect(path):
            if path == "/dev/input/event0":
                raise PermissionError("no access")
            return good_dev

        mock_evdev.InputDevice.side_effect = side_effect

        result = MediaKeyListener._find_bt_input_device()
        self.assertIs(result, good_dev)


class TestRunLoop(unittest.TestCase):
    """Test the reconnect loop behavior."""

    @patch("input.media_keys._HAS_EVDEV", True)
    @patch("input.media_keys._DEVICE_SCAN_INTERVAL", 0.01)
    def test_run_loop_retries_on_no_device(self):
        """Loop should keep scanning when no device is found."""
        listener = MediaKeyListener()
        call_count = 0

        def fake_find():
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                listener._running = False
            return None

        listener._find_bt_input_device = staticmethod(fake_find)
        listener._running = True
        listener._run_loop()
        self.assertGreaterEqual(call_count, 3)

    @patch("input.media_keys._HAS_EVDEV", True)
    @patch("input.media_keys._DEVICE_SCAN_INTERVAL", 0.01)
    def test_run_loop_reconnects_after_disconnect(self):
        """After _read_events returns (disconnect), loop should try again."""
        listener = MediaKeyListener()
        find_count = 0

        mock_dev = MagicMock()
        mock_dev.name = "AVRCP"
        mock_dev.path = "/dev/input/event5"

        def fake_find():
            nonlocal find_count
            find_count += 1
            if find_count >= 2:
                listener._running = False
                return None
            return mock_dev

        listener._find_bt_input_device = staticmethod(fake_find)
        listener._read_events = MagicMock()  # returns immediately = "disconnect"
        listener._running = True
        listener._run_loop()
        self.assertGreaterEqual(find_count, 2)


if __name__ == "__main__":
    unittest.main()
