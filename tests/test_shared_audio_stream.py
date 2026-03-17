"""Tests for SharedAudioStream — single-mic multi-consumer distribution."""

import os
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

import numpy as np
from audio.shared_stream import SharedAudioStream, SAMPLE_RATE, FRAME_SIZE, FORMAT_DTYPE


class TestSharedAudioStreamRegistration(unittest.TestCase):
    def test_register_returns_deque(self):
        stream = SharedAudioStream()
        buf = stream.register("test_consumer")
        self.assertIsNotNone(buf)
        self.assertEqual(len(buf), 0)

    def test_register_multiple_consumers(self):
        stream = SharedAudioStream()
        buf1 = stream.register("wake_word")
        buf2 = stream.register("recorder")
        buf3 = stream.register("vad")
        self.assertIsNot(buf1, buf2)
        self.assertIsNot(buf2, buf3)

    def test_unregister_removes_consumer(self):
        stream = SharedAudioStream()
        buf = stream.register("test")
        stream.unregister("test")
        # Distributing a frame should not populate the removed buffer
        frame = np.zeros(FRAME_SIZE, dtype=FORMAT_DTYPE)
        stream._distribute(frame)
        self.assertEqual(len(buf), 0)

    def test_unregister_nonexistent_is_noop(self):
        stream = SharedAudioStream()
        stream.unregister("nonexistent")  # should not raise

    def test_register_maxlen_limits_buffer(self):
        stream = SharedAudioStream()
        buf = stream.register("test", maxlen=3)
        frame = np.zeros(FRAME_SIZE, dtype=FORMAT_DTYPE)
        for _ in range(5):
            stream._distribute(frame)
        self.assertEqual(len(buf), 3)


class TestSharedAudioStreamDistribute(unittest.TestCase):
    def test_distribute_sends_to_all_consumers(self):
        stream = SharedAudioStream()
        buf1 = stream.register("a")
        buf2 = stream.register("b")
        frame = np.ones(FRAME_SIZE, dtype=FORMAT_DTYPE)
        stream._distribute(frame)
        self.assertEqual(len(buf1), 1)
        self.assertEqual(len(buf2), 1)
        np.testing.assert_array_equal(buf1[0], frame)
        np.testing.assert_array_equal(buf2[0], frame)

    def test_distribute_with_no_consumers(self):
        stream = SharedAudioStream()
        frame = np.zeros(FRAME_SIZE, dtype=FORMAT_DTYPE)
        stream._distribute(frame)  # should not raise


class TestSharedAudioStreamLifecycle(unittest.TestCase):
    def test_is_running_initially_false(self):
        stream = SharedAudioStream()
        self.assertFalse(stream.is_running)

    def test_properties(self):
        stream = SharedAudioStream(sample_rate=8000, frame_size=256)
        self.assertEqual(stream.sample_rate, 8000)
        self.assertEqual(stream.frame_size, 256)

    @patch("audio.shared_stream._HAS_PYAUDIO", False)
    def test_silence_fallback_generates_frames(self):
        """Without pyaudio, silence loop should generate frames."""
        stream = SharedAudioStream()
        buf = stream.register("test")
        stream.start()
        self.assertTrue(stream.is_running)
        # Give it time to generate some frames
        time.sleep(0.15)
        stream.stop()
        self.assertFalse(stream.is_running)
        self.assertGreater(len(buf), 0)
        # All frames should be silence (zeros)
        for frame in buf:
            self.assertTrue(np.all(frame == 0))

    def test_stop_without_start_is_safe(self):
        stream = SharedAudioStream()
        stream.stop()  # should not raise

    def test_double_start_is_idempotent(self):
        stream = SharedAudioStream()
        with patch.object(stream, "_read_loop"):
            stream._running = True
            stream.start()  # should return immediately


if __name__ == "__main__":
    unittest.main()
