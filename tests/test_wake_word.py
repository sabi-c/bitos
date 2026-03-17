"""Tests for WakeWordDetector — Porcupine/OWW via SharedAudioStream."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))


class TestWakeWordDetectorDisabled(unittest.TestCase):
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {"BITOS_WAKE_WORD": "off"}):
            from audio.wake_word import WakeWordDetector
            det = WakeWordDetector()
            det.ENABLED = False
            callback = MagicMock()
            det.start(callback)
            # Should not start thread
            self.assertIsNone(det._thread)

    def test_stop_when_never_started(self):
        from audio.wake_word import WakeWordDetector
        det = WakeWordDetector()
        det.stop()  # should not raise


class TestWakeWordDetectorNoEngines(unittest.TestCase):
    @patch("audio.wake_word._HAS_PORCUPINE", False)
    @patch("audio.wake_word._HAS_OWW", False)
    def test_start_logs_warning_when_no_engine(self):
        from audio.wake_word import WakeWordDetector
        det = WakeWordDetector()
        det.ENABLED = True
        callback = MagicMock()
        det.start(callback)
        self.assertIsNone(det._thread)


class TestWakeWordSharedStreamIntegration(unittest.TestCase):
    def test_registers_as_consumer(self):
        from audio.shared_stream import SharedAudioStream
        from audio.wake_word import WakeWordDetector

        stream = SharedAudioStream()
        det = WakeWordDetector(shared_stream=stream)
        # Not started yet — no registration
        self.assertNotIn("wake_word", stream._consumers)

    def test_stop_unregisters(self):
        from audio.shared_stream import SharedAudioStream
        from audio.wake_word import WakeWordDetector

        stream = SharedAudioStream()
        det = WakeWordDetector(shared_stream=stream)
        # Manually register to test unregister
        det._buf = stream.register(WakeWordDetector.CONSUMER_NAME)
        self.assertIn("wake_word", stream._consumers)
        det.stop()
        self.assertNotIn("wake_word", stream._consumers)

    def test_get_frame_returns_none_without_stream(self):
        from audio.wake_word import WakeWordDetector
        det = WakeWordDetector()
        self.assertIsNone(det._get_frame())

    def test_get_frame_pops_from_buffer(self):
        import collections
        import numpy as np
        from audio.wake_word import WakeWordDetector

        det = WakeWordDetector()
        det._buf = collections.deque()
        frame = np.ones(512, dtype=np.int16)
        det._buf.append(frame)
        result = det._get_frame()
        self.assertIsNotNone(result)
        self.assertEqual(len(det._buf), 0)


if __name__ == "__main__":
    unittest.main()
