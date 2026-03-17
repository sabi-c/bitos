"""Tests for VoiceActivityDetector — WebRTC VAD wrapper."""

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

import numpy as np


class TestVADWithoutWebrtcvad(unittest.TestCase):
    """Test graceful fallback when webrtcvad is not installed."""

    def test_unavailable_returns_true_for_is_speech(self):
        with patch.dict("sys.modules", {"webrtcvad": None}):
            # Force reimport
            import importlib
            import audio.vad as vad_mod
            # Simulate _HAS_VAD = False
            orig = vad_mod._HAS_VAD
            vad_mod._HAS_VAD = False
            try:
                detector = vad_mod.VoiceActivityDetector.__new__(vad_mod.VoiceActivityDetector)
                detector._sample_rate = 16000
                detector._vad = None
                self.assertFalse(detector.available)
                frame = np.zeros(512, dtype=np.int16)
                self.assertTrue(detector.is_speech(frame))
            finally:
                vad_mod._HAS_VAD = orig

    def test_trim_silence_returns_original_when_unavailable(self):
        from audio.vad import VoiceActivityDetector
        det = VoiceActivityDetector.__new__(VoiceActivityDetector)
        det._sample_rate = 16000
        det._vad = None
        audio = np.zeros(16000, dtype=np.int16)
        result = det.trim_silence(audio)
        np.testing.assert_array_equal(result, audio)

    def test_detect_silence_returns_zero_when_unavailable(self):
        from audio.vad import VoiceActivityDetector
        det = VoiceActivityDetector.__new__(VoiceActivityDetector)
        det._sample_rate = 16000
        det._vad = None
        self.assertEqual(det.detect_silence_duration([]), 0.0)
        frame = np.zeros(512, dtype=np.int16)
        self.assertEqual(det.detect_silence_duration([frame]), 0.0)


class TestVADWithMockedWebrtcvad(unittest.TestCase):
    """Test VAD logic with a mocked webrtcvad backend."""

    def _make_detector(self, speech_fn):
        from audio.vad import VoiceActivityDetector
        det = VoiceActivityDetector.__new__(VoiceActivityDetector)
        det._sample_rate = 16000
        mock_vad = MagicMock()
        mock_vad.is_speech = speech_fn
        det._vad = mock_vad
        return det

    def test_is_speech_delegates_to_vad(self):
        det = self._make_detector(lambda buf, sr: True)
        frame = np.ones(512, dtype=np.int16)
        self.assertTrue(det.is_speech(frame))

    def test_is_speech_returns_true_on_short_frame(self):
        """Frames shorter than 480 samples should default to True."""
        det = self._make_detector(lambda buf, sr: False)
        short = np.zeros(100, dtype=np.int16)
        self.assertTrue(det.is_speech(short))

    def test_is_speech_returns_true_on_exception(self):
        def bad_vad(buf, sr):
            raise RuntimeError("boom")
        det = self._make_detector(bad_vad)
        frame = np.zeros(512, dtype=np.int16)
        self.assertTrue(det.is_speech(frame))

    def test_available_property(self):
        det = self._make_detector(lambda b, s: True)
        self.assertTrue(det.available)

    def test_detect_silence_duration_all_silence(self):
        det = self._make_detector(lambda buf, sr: False)
        frames = [np.zeros(512, dtype=np.int16) for _ in range(10)]
        duration = det.detect_silence_duration(frames)
        expected = 10 * 512 / 16000
        self.assertAlmostEqual(duration, expected, places=3)

    def test_detect_silence_duration_with_speech(self):
        # 7 speech frames followed by 3 silence frames
        # detect_silence_duration iterates in reverse, so we make the mock
        # return False for the first 3 calls (trailing silence) then True.
        reverse_call = [0]
        def speech_reverse(buf, sr):
            reverse_call[0] += 1
            # Called in reverse order: first 3 calls = trailing frames = silence
            return reverse_call[0] > 3

        det = self._make_detector(speech_reverse)
        frames = [np.zeros(512, dtype=np.int16) for _ in range(10)]
        duration = det.detect_silence_duration(frames)
        expected = 3 * 512 / 16000
        self.assertAlmostEqual(duration, expected, places=3)

    def test_detect_silence_empty_buffer(self):
        det = self._make_detector(lambda b, s: True)
        self.assertEqual(det.detect_silence_duration([]), 0.0)

    def test_trim_silence_keeps_speech_with_margins(self):
        # Build audio: 5 silent frames, 3 speech frames, 5 silent frames
        # at 30ms frames = 480 samples each
        frame_samples = 480
        silent = np.zeros(frame_samples, dtype=np.int16)
        speech = np.ones(frame_samples, dtype=np.int16) * 1000

        audio = np.concatenate(
            [silent] * 5 + [speech] * 3 + [silent] * 5
        )

        call_count = [0]
        def mock_is_speech(buf, sr):
            # Determine based on content
            arr = np.frombuffer(buf, dtype=np.int16)
            return np.any(arr != 0)

        det = self._make_detector(mock_is_speech)
        trimmed = det.trim_silence(audio, frame_ms=30)
        # Should be shorter than original
        self.assertLess(len(trimmed), len(audio))
        # Should contain the speech frames
        self.assertTrue(np.any(trimmed != 0))

    def test_trim_silence_returns_original_if_result_too_short(self):
        """If trimming would produce fewer than frame_samples, return original."""
        det = self._make_detector(lambda buf, sr: False)
        audio = np.zeros(480, dtype=np.int16)  # exactly 1 frame, all silence
        result = det.trim_silence(audio, frame_ms=30)
        np.testing.assert_array_equal(result, audio)


if __name__ == "__main__":
    unittest.main()
