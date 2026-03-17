"""Tests for VoiceRecorder — VAD-based recording with SharedAudioStream."""

import os
import sys
import time
import threading
import unittest
import wave
import io
from collections import deque
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

import numpy as np

from audio.voice_recorder import VoiceRecorder, RecorderState, SAMPLE_RATE, FRAME_SIZE


class FakeSharedStream:
    """Mock SharedAudioStream that feeds controllable frames."""

    def __init__(self):
        self._consumers: dict[str, deque] = {}
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def register(self, name: str, maxlen: int = 100) -> deque:
        buf = deque(maxlen=maxlen)
        self._consumers[name] = buf
        return buf

    def unregister(self, name: str) -> None:
        self._consumers.pop(name, None)

    def start(self) -> None:
        self._running = True

    def stop(self) -> None:
        self._running = False

    def push_frame(self, frame: np.ndarray) -> None:
        """Push a frame to all consumers."""
        for buf in self._consumers.values():
            buf.append(frame)

    def push_silence(self, n: int = 1) -> None:
        """Push n silent frames."""
        for _ in range(n):
            self.push_frame(np.zeros(FRAME_SIZE, dtype=np.int16))

    def push_speech(self, n: int = 1, amplitude: int = 5000) -> None:
        """Push n frames with speech-level amplitude."""
        for _ in range(n):
            frame = (np.random.randn(FRAME_SIZE) * amplitude).astype(np.int16)
            self.push_frame(frame)


class VoiceRecorderTests(unittest.TestCase):

    def test_initial_state_is_idle(self):
        stream = FakeSharedStream()
        rec = VoiceRecorder(stream)
        self.assertEqual(rec.state, RecorderState.IDLE)

    def test_start_transitions_to_recording(self):
        stream = FakeSharedStream()
        rec = VoiceRecorder(stream, silence_timeout=0.3, max_duration=2.0)
        ok = rec.start()
        self.assertTrue(ok)
        self.assertEqual(rec.state, RecorderState.RECORDING)
        # Cleanup
        rec.stop()

    def test_start_fails_when_already_recording(self):
        stream = FakeSharedStream()
        rec = VoiceRecorder(stream, silence_timeout=0.3, max_duration=2.0)
        rec.start()
        self.assertFalse(rec.start())
        rec.stop()

    def test_stop_cancels_recording(self):
        stream = FakeSharedStream()
        done_event = threading.Event()
        result_holder = [None]

        def on_done(wav):
            result_holder[0] = wav
            done_event.set()

        rec = VoiceRecorder(stream, on_done=on_done, silence_timeout=0.3)
        rec.start()
        time.sleep(0.05)
        rec.stop()
        done_event.wait(timeout=2.0)
        self.assertIsNone(result_holder[0])
        self.assertEqual(rec.state, RecorderState.IDLE)

    @patch("audio.vad.VoiceActivityDetector")
    def test_silence_endpoint_produces_wav(self, mock_vad_class):
        """After speech + silence, recorder produces valid WAV bytes."""
        mock_vad = MagicMock()
        mock_vad.is_speech = MagicMock(side_effect=lambda f: True)
        mock_vad_class.return_value = mock_vad

        stream = FakeSharedStream()
        done_event = threading.Event()
        result_holder = [None]

        def on_done(wav):
            result_holder[0] = wav
            done_event.set()

        rec = VoiceRecorder(
            stream,
            on_done=on_done,
            silence_timeout=0.15,
            max_duration=5.0,
        )
        rec.start()
        time.sleep(0.05)

        # Push speech frames
        stream.push_speech(n=10)
        time.sleep(0.1)

        # Now switch VAD to return silence and keep feeding over time
        mock_vad.is_speech = MagicMock(return_value=False)
        for _ in range(10):
            stream.push_silence(n=3)
            time.sleep(0.05)

        # Wait for silence timeout + processing
        done_event.wait(timeout=3.0)
        self.assertTrue(done_event.is_set(), "on_done was not called")

        wav_bytes = result_holder[0]
        self.assertIsNotNone(wav_bytes)
        self.assertGreater(len(wav_bytes), 44)  # WAV header is 44 bytes

        # Verify it's valid WAV
        with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
            self.assertEqual(wf.getnchannels(), 1)
            self.assertEqual(wf.getframerate(), SAMPLE_RATE)
            self.assertEqual(wf.getsampwidth(), 2)

    @patch("audio.vad.VoiceActivityDetector")
    def test_force_send_stops_early(self, mock_vad_class):
        """force_send() ends recording before silence timeout."""
        mock_vad = MagicMock()
        mock_vad.is_speech = MagicMock(return_value=True)
        mock_vad_class.return_value = mock_vad

        stream = FakeSharedStream()
        done_event = threading.Event()
        result_holder = [None]

        def on_done(wav):
            result_holder[0] = wav
            done_event.set()

        rec = VoiceRecorder(
            stream,
            on_done=on_done,
            silence_timeout=10.0,  # very long — force_send should bypass
            max_duration=30.0,
        )
        rec.start()
        time.sleep(0.05)

        # Push speech frames
        stream.push_speech(n=10)
        time.sleep(0.1)

        rec.force_send()
        done_event.wait(timeout=2.0)
        self.assertTrue(done_event.is_set())
        self.assertIsNotNone(result_holder[0])

    @patch("audio.vad.VoiceActivityDetector")
    def test_too_few_speech_frames_returns_none(self, mock_vad_class):
        """If not enough speech is detected, result is None."""
        mock_vad = MagicMock()
        mock_vad.is_speech = MagicMock(return_value=False)  # always silence
        mock_vad_class.return_value = mock_vad

        stream = FakeSharedStream()
        done_event = threading.Event()
        result_holder = ["sentinel"]

        def on_done(wav):
            result_holder[0] = wav
            done_event.set()

        rec = VoiceRecorder(
            stream,
            on_done=on_done,
            silence_timeout=0.1,
            max_duration=0.5,
        )
        rec.start()
        time.sleep(0.05)
        stream.push_silence(n=5)

        done_event.wait(timeout=2.0)
        self.assertIsNone(result_holder[0])

    def test_amplitude_callback(self):
        """on_amplitude is called with RMS values during recording."""
        stream = FakeSharedStream()
        amplitudes = []

        def on_amp(val):
            amplitudes.append(val)

        rec = VoiceRecorder(
            stream,
            on_amplitude=on_amp,
            silence_timeout=0.2,
            max_duration=1.0,
        )
        rec.start()
        time.sleep(0.05)
        stream.push_speech(n=3, amplitude=10000)
        time.sleep(0.2)
        rec.stop()

        self.assertGreater(len(amplitudes), 0)
        # All amplitudes should be 0-1 range
        for a in amplitudes:
            self.assertGreaterEqual(a, 0.0)
            self.assertLessEqual(a, 1.0)

    @patch("audio.vad.VoiceActivityDetector")
    def test_max_duration_timeout(self, mock_vad_class):
        """Recording stops at max_duration even if speech continues."""
        mock_vad = MagicMock()
        mock_vad.is_speech = MagicMock(return_value=True)
        mock_vad_class.return_value = mock_vad

        stream = FakeSharedStream()
        done_event = threading.Event()

        rec = VoiceRecorder(
            stream,
            on_done=lambda wav: done_event.set(),
            silence_timeout=10.0,
            max_duration=0.3,  # very short
        )
        rec.start()

        # Keep feeding speech
        def feeder():
            while not done_event.is_set():
                stream.push_speech(n=2)
                time.sleep(0.02)

        t = threading.Thread(target=feeder, daemon=True)
        t.start()

        done_event.wait(timeout=2.0)
        self.assertTrue(done_event.is_set(), "Recording didn't stop at max_duration")


if __name__ == "__main__":
    unittest.main()
