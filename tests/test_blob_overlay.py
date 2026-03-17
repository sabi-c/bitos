"""Tests for BlobOverlay — voice pipeline overlay lifecycle and state machine."""

import os
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

import pygame

from overlays.blob_overlay import BlobOverlay, BlobOverlayState


class FakeClient:
    """Mock BackendClient that returns a streaming response."""

    def __init__(self, response_chunks=None, error=None):
        self._chunks = response_chunks or ["Hello ", "world!"]
        self._error = error

    def chat(self, message):
        if self._error:
            return {"error": self._error}
        return iter(self._chunks)


class FakeAudioPipeline:
    """Mock AudioPipeline."""

    def __init__(self):
        self._speaking = False
        self._stopped = threading.Event()
        self.speak_called = False
        self.transcribe_result = "hello world"

    def record(self, max_seconds=60):
        return "/tmp/fake_rec.wav"

    def stop_recording(self):
        pass

    def transcribe(self, path):
        return self.transcribe_result

    def speak(self, text):
        self.speak_called = True
        self._speaking = True
        self._stopped.clear()
        self._stopped.wait(timeout=1.0)
        self._speaking = False

    def is_speaking(self):
        return self._speaking

    def stop_speaking(self):
        self._speaking = False
        self._stopped.set()


class FakeSharedStream:
    """Mock SharedAudioStream."""

    def __init__(self):
        self._running = False

    @property
    def is_running(self):
        return self._running

    def register(self, name, maxlen=100):
        from collections import deque
        return deque(maxlen=maxlen)

    def unregister(self, name):
        pass

    def start(self):
        self._running = True


class BlobOverlayLifecycleTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.surface = pygame.Surface((240, 280))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _make_overlay(self, client=None, pipeline=None, stream=None):
        """Create a BlobOverlay with __post_init__ recording disabled."""
        c = client or FakeClient()
        p = pipeline or FakeAudioPipeline()
        s = stream or FakeSharedStream()

        # Temporarily disable __post_init__ to control start manually
        with patch.object(BlobOverlay, '__post_init__', lambda self: None):
            overlay = BlobOverlay(
                client=c,
                audio_pipeline=p,
                shared_stream=s,
            )
        return overlay

    def test_initial_state_is_listening(self):
        overlay = self._make_overlay()
        self.assertEqual(overlay._state, BlobOverlayState.LISTENING)

    def test_tick_returns_true_while_active(self):
        overlay = self._make_overlay()
        self.assertTrue(overlay.tick(16))

    def test_dismiss_sets_dismissed(self):
        overlay = self._make_overlay()
        overlay._dismiss()
        self.assertTrue(overlay.dismissed)
        self.assertFalse(overlay.tick(16))

    def test_short_press_during_listening_dismisses(self):
        overlay = self._make_overlay()
        consumed = overlay.handle_action("SHORT_PRESS")
        self.assertTrue(consumed)
        self.assertTrue(overlay.dismissed)

    def test_double_press_during_listening_force_sends(self):
        """DOUBLE_PRESS during LISTENING should trigger force send."""
        overlay = self._make_overlay()
        # Mock the recorder
        mock_recorder = MagicMock()
        overlay._recorder = mock_recorder
        consumed = overlay.handle_action("DOUBLE_PRESS")
        self.assertTrue(consumed)
        mock_recorder.force_send.assert_called_once()

    def test_long_press_dismisses(self):
        overlay = self._make_overlay()
        overlay.handle_action("LONG_PRESS")
        self.assertTrue(overlay.dismissed)

    def test_triple_press_dismisses(self):
        overlay = self._make_overlay()
        overlay.handle_action("TRIPLE_PRESS")
        self.assertTrue(overlay.dismissed)

    def test_auto_dismiss_after_done_timeout(self):
        overlay = self._make_overlay()
        overlay._state = BlobOverlayState.DONE
        overlay._done_elapsed_ms = 0

        # Tick past the auto-dismiss threshold
        overlay.tick(overlay.auto_dismiss_ms + 100)
        self.assertTrue(overlay.dismissed)

    def test_done_state_does_not_dismiss_early(self):
        overlay = self._make_overlay()
        overlay._state = BlobOverlayState.DONE
        overlay._done_elapsed_ms = 0

        # Tick but not enough to trigger auto-dismiss
        overlay.tick(100)
        self.assertFalse(overlay.dismissed)

    def test_double_press_during_speaking_stops_tts(self):
        pipeline = FakeAudioPipeline()
        overlay = self._make_overlay(pipeline=pipeline)
        overlay._state = BlobOverlayState.SPEAKING
        pipeline._speaking = True

        consumed = overlay.handle_action("DOUBLE_PRESS")
        self.assertTrue(consumed)
        # Should have stopped TTS
        self.assertFalse(pipeline.is_speaking())

    def test_short_press_during_done_dismisses(self):
        overlay = self._make_overlay()
        overlay._state = BlobOverlayState.DONE
        consumed = overlay.handle_action("SHORT_PRESS")
        self.assertTrue(consumed)
        self.assertTrue(overlay.dismissed)

    def test_render_does_not_crash(self):
        """Render in each state without crashing."""
        overlay = self._make_overlay()

        for state in BlobOverlayState:
            overlay._state = state
            overlay._dismissed = False
            overlay._response = "Test response text"
            overlay._transcript = "test transcript"
            overlay._error = "test error" if state == BlobOverlayState.DONE else ""
            try:
                overlay.render(self.surface)
            except Exception as exc:
                self.fail(f"render() crashed in state {state}: {exc}")

    def test_render_skips_when_dismissed(self):
        overlay = self._make_overlay()
        overlay._dismissed = True
        # Should not crash, should be a no-op
        overlay.render(self.surface)

    def test_set_error_transitions_to_done(self):
        overlay = self._make_overlay()
        overlay._set_error("mic broken")
        self.assertEqual(overlay._state, BlobOverlayState.DONE)
        self.assertEqual(overlay._error, "mic broken")

    def test_set_done_transitions_state(self):
        overlay = self._make_overlay()
        overlay._state = BlobOverlayState.SPEAKING
        overlay._set_done()
        self.assertEqual(overlay._state, BlobOverlayState.DONE)
        self.assertEqual(overlay._done_elapsed_ms, 0)

    def test_hold_actions_consumed(self):
        overlay = self._make_overlay()
        self.assertTrue(overlay.handle_action("HOLD_START"))
        self.assertTrue(overlay.handle_action("HOLD_END"))

    def test_handle_action_returns_false_when_dismissed(self):
        overlay = self._make_overlay()
        overlay._dismissed = True
        self.assertFalse(overlay.handle_action("SHORT_PRESS"))


class BlobOverlayPipelineTests(unittest.TestCase):
    """Test the voice -> STT -> chat -> TTS pipeline."""

    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_process_audio_full_pipeline(self):
        """process_audio transcribes, chats, and reaches DONE."""
        client = FakeClient(response_chunks=["Hey ", "there!"])
        pipeline = FakeAudioPipeline()

        with patch.object(BlobOverlay, '__post_init__', lambda self: None):
            overlay = BlobOverlay(
                client=client,
                audio_pipeline=pipeline,
                shared_stream=FakeSharedStream(),
            )

        # Create minimal WAV bytes
        import io
        import wave
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00" * 3200)
        wav_bytes = wav_buf.getvalue()

        # Run _process_audio in a thread
        t = threading.Thread(target=overlay._process_audio, args=(wav_bytes,))
        t.start()
        t.join(timeout=5.0)

        self.assertEqual(overlay._state, BlobOverlayState.DONE)
        self.assertEqual(overlay._transcript, "hello world")
        self.assertIn("Hey there!", overlay._response)
        self.assertTrue(pipeline.speak_called)

    def test_process_audio_handles_chat_error(self):
        """Chat error transitions to DONE with error message."""
        client = FakeClient(error="Server offline")
        pipeline = FakeAudioPipeline()

        with patch.object(BlobOverlay, '__post_init__', lambda self: None):
            overlay = BlobOverlay(
                client=client,
                audio_pipeline=pipeline,
                shared_stream=FakeSharedStream(),
            )

        import io, wave
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00" * 3200)

        overlay._process_audio(wav_buf.getvalue())
        self.assertEqual(overlay._state, BlobOverlayState.DONE)
        self.assertIn("Server offline", overlay._error)

    def test_process_audio_empty_transcript(self):
        """No transcript -> error."""
        client = FakeClient()
        pipeline = FakeAudioPipeline()
        pipeline.transcribe_result = ""

        with patch.object(BlobOverlay, '__post_init__', lambda self: None):
            overlay = BlobOverlay(
                client=client,
                audio_pipeline=pipeline,
                shared_stream=FakeSharedStream(),
            )

        import io, wave
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(b"\x00" * 3200)

        overlay._process_audio(wav_buf.getvalue())
        self.assertEqual(overlay._state, BlobOverlayState.DONE)
        self.assertEqual(overlay._error, "no speech")


if __name__ == "__main__":
    unittest.main()
