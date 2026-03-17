"""Tests for the voice blob overlay and blob renderer."""

import os
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

import pygame

pygame.init()

from blob.renderer import BlobRendererLite, BlobState
from overlays.blob_overlay import BlobOverlay, VoiceOverlayState


class TestBlobRendererLite(unittest.TestCase):
    """Unit tests for the lightweight blob renderer."""

    def setUp(self):
        self.surface = pygame.Surface((240, 280))
        self.renderer = BlobRendererLite(cx=120, cy=90, base_radius=32)

    def test_initial_state_is_idle(self):
        self.assertEqual(self.renderer.state, BlobState.IDLE)

    def test_set_state(self):
        for state in BlobState:
            self.renderer.set_state(state)
            self.assertEqual(self.renderer.state, state)

    def test_set_amplitude_clamps(self):
        self.renderer.set_amplitude(-0.5)
        self.assertEqual(self.renderer.amplitude, 0.0)
        self.renderer.set_amplitude(1.5)
        self.assertEqual(self.renderer.amplitude, 1.0)
        self.renderer.set_amplitude(0.7)
        self.assertAlmostEqual(self.renderer.amplitude, 0.7)

    def test_render_does_not_crash_any_state(self):
        for state in BlobState:
            self.renderer.set_state(state)
            self.renderer.set_amplitude(0.5)
            self.renderer.render(self.surface)

    def test_render_glow_does_not_crash(self):
        self.renderer.render_glow(self.surface)

    def test_render_with_amplitude(self):
        self.renderer.set_state(BlobState.LISTENING)
        self.renderer.set_amplitude(0.8)
        self.renderer.render(self.surface)  # Should not crash

    def test_custom_position_and_radius(self):
        r = BlobRendererLite(cx=50, cy=50, base_radius=20)
        self.assertEqual(r.cx, 50)
        self.assertEqual(r.cy, 50)
        self.assertEqual(r.base_radius, 20)
        r.render(self.surface)  # Should not crash


class MockPipeline:
    """Mock audio pipeline for testing."""

    def __init__(self):
        self._recording = False
        self._speaking = False
        self.transcript = "hello test"
        self.speak_called = False
        self._stop_event = threading.Event()

    def record(self, max_seconds=60):
        self._recording = True
        import tempfile
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        # Write a minimal WAV file (44-byte header + some data)
        import struct
        import wave
        with wave.open(path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            # Write 0.1s of silence
            wf.writeframes(b"\x00\x00" * 1600)
        return path

    def stop_recording(self):
        self._recording = False

    def transcribe(self, audio_path):
        return self.transcript

    def speak(self, text):
        self.speak_called = True
        self._speaking = True
        self._stop_event.clear()
        self._stop_event.wait(timeout=0.1)
        self._speaking = False

    def is_speaking(self):
        return self._speaking

    def stop_speaking(self):
        self._speaking = False
        self._stop_event.set()

    def is_available(self):
        return True


class MockClient:
    """Mock backend client for testing."""

    def __init__(self, response_chunks=None):
        self.response_chunks = response_chunks or ["Hello ", "world!"]
        self.last_message = None

    def chat(self, message):
        self.last_message = message
        return iter(self.response_chunks)


class TestBlobOverlay(unittest.TestCase):
    """Integration tests for the blob voice overlay."""

    def _make_overlay(self, pipeline=None, client=None):
        return BlobOverlay(
            audio_pipeline=pipeline or MockPipeline(),
            client=client or MockClient(),
            led=MagicMock(),
        )

    def test_initial_state(self):
        ov = self._make_overlay()
        self.assertEqual(ov.state, VoiceOverlayState.IDLE)
        self.assertFalse(ov.dismissed)

    def test_tick_keeps_alive(self):
        ov = self._make_overlay()
        self.assertTrue(ov.tick(16))
        self.assertTrue(ov.tick(16))

    def test_dismiss_on_double_press(self):
        ov = self._make_overlay()
        ov.handle_action("DOUBLE_PRESS")
        self.assertTrue(ov.dismissed)

    def test_dismiss_on_long_press(self):
        ov = self._make_overlay()
        ov.handle_action("LONG_PRESS")
        self.assertTrue(ov.dismissed)

    def test_dismiss_on_triple_press(self):
        ov = self._make_overlay()
        ov.handle_action("TRIPLE_PRESS")
        self.assertTrue(ov.dismissed)

    def test_short_press_starts_listening(self):
        ov = self._make_overlay()
        ov.handle_action("SHORT_PRESS")
        # Give thread a moment to start
        time.sleep(0.05)
        self.assertEqual(ov.state, VoiceOverlayState.LISTENING)

    def test_short_press_while_listening_triggers_send(self):
        pipeline = MockPipeline()
        client = MockClient()
        ov = self._make_overlay(pipeline=pipeline, client=client)

        # Start listening
        ov.handle_action("SHORT_PRESS")
        time.sleep(0.05)

        # Stop listening (send)
        ov.handle_action("SHORT_PRESS")
        # Wait for voice flow to complete
        time.sleep(0.5)

        self.assertEqual(client.last_message, "hello test")

    def test_full_voice_cycle(self):
        """Test the complete IDLE -> LISTENING -> THINKING -> SPEAKING -> DONE flow."""
        pipeline = MockPipeline()
        client = MockClient(response_chunks=["Test response"])
        ov = self._make_overlay(pipeline=pipeline, client=client)

        # Start
        self.assertEqual(ov.state, VoiceOverlayState.IDLE)

        # Tap to record
        ov.handle_action("SHORT_PRESS")
        time.sleep(0.05)
        self.assertEqual(ov.state, VoiceOverlayState.LISTENING)

        # Tap to send
        ov.handle_action("SHORT_PRESS")

        # Wait for full pipeline (transcribe + chat + speak)
        for _ in range(100):
            time.sleep(0.05)
            if ov.state == VoiceOverlayState.DONE:
                break

        self.assertEqual(ov.state, VoiceOverlayState.DONE)
        self.assertTrue(pipeline.speak_called)

    def test_render_does_not_crash_all_states(self):
        """Rendering should work in every state without crashing."""
        # Re-init pygame in case a prior test class called pygame.quit()
        if not pygame.get_init():
            pygame.init()
        surface = pygame.Surface((240, 280), pygame.SRCALPHA)
        ov = self._make_overlay()

        # Manually set states and render
        for state in VoiceOverlayState:
            with ov._lock:
                ov._state = state
            ov._transcript = "test transcript"
            ov._response = "test response text"
            ov.render(surface)

    def test_render_with_error(self):
        if not pygame.get_init():
            pygame.init()
        surface = pygame.Surface((240, 280), pygame.SRCALPHA)
        ov = self._make_overlay()
        with ov._lock:
            ov._state = VoiceOverlayState.DONE
            ov._error = "test error"
        ov.render(surface)

    def test_auto_dismiss_after_timeout_in_done(self):
        ov = self._make_overlay()
        ov.timeout_ms = 100  # Short timeout for test
        with ov._lock:
            ov._state = VoiceOverlayState.DONE
        # Tick past timeout
        ov.tick(50)
        self.assertFalse(ov.dismissed)
        ov.tick(60)  # Total > 100ms
        self.assertTrue(ov.dismissed)

    def test_dismiss_callback_fires(self):
        callback = MagicMock()
        ov = self._make_overlay()
        ov.on_dismiss = callback
        ov._dismiss()
        callback.assert_called_once()

    def test_handles_no_pipeline_gracefully(self):
        ov = BlobOverlay(
            audio_pipeline=None,
            client=MockClient(),
        )
        ov.handle_action("SHORT_PRESS")
        time.sleep(0.05)
        self.assertEqual(ov.state, VoiceOverlayState.DONE)
        self.assertEqual(ov._error, "no mic")

    def test_consume_hold_events(self):
        ov = self._make_overlay()
        self.assertTrue(ov.handle_action("HOLD_START"))
        self.assertTrue(ov.handle_action("HOLD_END"))

    def test_does_not_handle_after_dismiss(self):
        ov = self._make_overlay()
        ov._dismiss()
        self.assertFalse(ov.handle_action("SHORT_PRESS"))

    def test_stop_speaking_transitions_to_done(self):
        pipeline = MockPipeline()
        ov = self._make_overlay(pipeline=pipeline)
        with ov._lock:
            ov._state = VoiceOverlayState.SPEAKING
        ov.handle_action("SHORT_PRESS")
        self.assertEqual(ov.state, VoiceOverlayState.DONE)


class TestBlobOverlayStateTransitions(unittest.TestCase):
    """Test state transitions map to correct blob states."""

    def test_blob_state_follows_overlay_state(self):
        pipeline = MockPipeline()
        ov = BlobOverlay(
            audio_pipeline=pipeline,
            client=MockClient(),
            led=MagicMock(),
        )

        # IDLE -> blob IDLE
        self.assertEqual(ov._blob.state, BlobState.IDLE)

        # Start listening -> blob LISTENING
        ov.handle_action("SHORT_PRESS")
        time.sleep(0.05)
        self.assertEqual(ov._blob.state, BlobState.LISTENING)

        # Stop listening -> blob THINKING (after transcription starts)
        ov.handle_action("SHORT_PRESS")
        time.sleep(0.2)
        # Should be THINKING or beyond
        self.assertIn(ov._blob.state, [BlobState.THINKING, BlobState.SPEAKING, BlobState.IDLE])


if __name__ == "__main__":
    unittest.main()
