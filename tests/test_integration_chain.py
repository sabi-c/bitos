"""Integration tests for the end-to-end chains.

Tests the key integration paths:
1. BT gesture → AAP mapper → ButtonEvent dispatch
2. Voice overlay lifecycle (push, record, send, receive, TTS, dismiss)
3. navigate_to tool → setting_change → device screen open
"""

import json
import os
import sys
import threading
import time
import unittest
from collections import deque
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock, call

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

import pygame


# ── Shared Fakes ──────────────────────────────────────────────────────

class FakeClient:
    """Mock BackendClient that returns streaming response."""

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
        self.speak_called = False
        self.transcribe_result = "hello world"

    def transcribe(self, path):
        return self.transcribe_result

    def speak(self, text):
        self.speak_called = True
        self._speaking = True
        time.sleep(0.05)
        self._speaking = False

    def is_speaking(self):
        return self._speaking

    def stop_speaking(self):
        self._speaking = False

    def stop_recording(self):
        pass


class FakeSharedStream:
    """Mock SharedAudioStream."""

    def __init__(self):
        self._running = False
        self._consumers = {}

    @property
    def is_running(self):
        return self._running

    def register(self, name, maxlen=100):
        buf = deque(maxlen=maxlen)
        self._consumers[name] = buf
        return buf

    def unregister(self, name):
        self._consumers.pop(name, None)

    def start(self):
        self._running = True


# ══════════════════════════════════════════════════════════════════════
# 1. BT Gesture → Button Event Dispatch
# ══════════════════════════════════════════════════════════════════════

class AAPGestureToButtonTests(unittest.TestCase):
    """Test that AAP stem presses map correctly to BITOS ButtonEvents."""

    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_default_mapping_single_to_double_press(self):
        """Single stem press maps to DOUBLE_PRESS (select)."""
        from bluetooth.aap_gesture_mapper import AAPGestureMapper
        from input.handler import ButtonEvent

        received = []
        mapper = AAPGestureMapper(on_button=lambda btn: received.append(btn))
        mapper.active = True

        mapper.on_stem_press(0x05)  # SINGLE
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], ButtonEvent.DOUBLE_PRESS)

    def test_default_mapping_double_to_short_press(self):
        """Double stem press maps to SHORT_PRESS (next item)."""
        from bluetooth.aap_gesture_mapper import AAPGestureMapper
        from input.handler import ButtonEvent

        received = []
        mapper = AAPGestureMapper(on_button=lambda btn: received.append(btn))
        mapper.active = True

        mapper.on_stem_press(0x06)  # DOUBLE
        self.assertEqual(received[0], ButtonEvent.SHORT_PRESS)

    def test_default_mapping_triple_to_long_press(self):
        """Triple stem press maps to LONG_PRESS (go back)."""
        from bluetooth.aap_gesture_mapper import AAPGestureMapper
        from input.handler import ButtonEvent

        received = []
        mapper = AAPGestureMapper(on_button=lambda btn: received.append(btn))
        mapper.active = True

        mapper.on_stem_press(0x07)  # TRIPLE
        self.assertEqual(received[0], ButtonEvent.LONG_PRESS)

    def test_default_mapping_long_to_triple_press(self):
        """Long stem press maps to TRIPLE_PRESS (agent overlay)."""
        from bluetooth.aap_gesture_mapper import AAPGestureMapper
        from input.handler import ButtonEvent

        received = []
        mapper = AAPGestureMapper(on_button=lambda btn: received.append(btn))
        mapper.active = True

        mapper.on_stem_press(0x08)  # LONG
        self.assertEqual(received[0], ButtonEvent.TRIPLE_PRESS)

    def test_mapper_inactive_ignores_events(self):
        """When mapper is inactive, stem presses are ignored."""
        from bluetooth.aap_gesture_mapper import AAPGestureMapper

        received = []
        mapper = AAPGestureMapper(on_button=lambda btn: received.append(btn))
        mapper.active = False

        mapper.on_stem_press(0x05)
        self.assertEqual(len(received), 0)

    def test_unknown_press_value_ignored(self):
        """Unknown press value does not crash or dispatch."""
        from bluetooth.aap_gesture_mapper import AAPGestureMapper

        received = []
        mapper = AAPGestureMapper(on_button=lambda btn: received.append(btn))
        mapper.active = True

        mapper.on_stem_press(0xFF)  # Unknown
        self.assertEqual(len(received), 0)

    def test_aap_client_fires_stem_press_callback(self):
        """AAPClient._check_stem_press dispatches to callback."""
        from bluetooth.aap_client import AAPClient

        client = AAPClient()
        received = []
        client.on_stem_press = lambda val: received.append(val)

        # Craft a packet with a stem press byte at offset 6
        # Header is 6 bytes of arbitrary data, then the press type byte
        packet = bytes([0x04, 0x00, 0x04, 0x00, 0x01, 0x02, 0x07])  # 0x07 = TRIPLE
        client._check_stem_press(packet)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], 0x07)

    def test_full_chain_aap_press_to_button_event(self):
        """End-to-end: AAP packet → mapper → ButtonEvent."""
        from bluetooth.aap_client import AAPClient
        from bluetooth.aap_gesture_mapper import AAPGestureMapper
        from input.handler import ButtonEvent

        button_events = []
        mapper = AAPGestureMapper(on_button=lambda btn: button_events.append(btn))
        mapper.active = True

        client = AAPClient()
        client.on_stem_press = mapper.on_stem_press

        # Simulate long press packet (0x08 at offset 6)
        packet = bytes([0x04, 0x00, 0x04, 0x00, 0x01, 0x02, 0x08])
        client._check_stem_press(packet)

        self.assertEqual(len(button_events), 1)
        self.assertEqual(button_events[0], ButtonEvent.TRIPLE_PRESS)


# ══════════════════════════════════════════════════════════════════════
# 2. Voice Overlay Lifecycle
# ══════════════════════════════════════════════════════════════════════

class BlobOverlayLifecycleIntegrationTests(unittest.TestCase):
    """Test the BlobOverlay voice pipeline lifecycle."""

    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.surface = pygame.Surface((240, 280))

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def _make_overlay(self, client=None, pipeline=None, stream=None):
        from overlays.blob_overlay import BlobOverlay
        c = client or FakeClient()
        p = pipeline or FakeAudioPipeline()
        s = stream or FakeSharedStream()
        with patch.object(BlobOverlay, '__post_init__', lambda self: None):
            overlay = BlobOverlay(client=c, audio_pipeline=p, shared_stream=s)
        return overlay

    def test_push_starts_listening(self):
        """Overlay starts in LISTENING state."""
        from overlays.blob_overlay import BlobOverlayState
        overlay = self._make_overlay()
        self.assertEqual(overlay._state, BlobOverlayState.LISTENING)

    def test_tick_keeps_alive_while_active(self):
        overlay = self._make_overlay()
        self.assertTrue(overlay.tick(16))
        self.assertTrue(overlay.tick(16))

    def test_dismiss_on_long_press(self):
        overlay = self._make_overlay()
        overlay.handle_action("LONG_PRESS")
        self.assertTrue(overlay.dismissed)
        self.assertFalse(overlay.tick(16))

    def test_dismiss_on_triple_press_toggle(self):
        """TRIPLE_PRESS should dismiss (toggle off)."""
        overlay = self._make_overlay()
        overlay.handle_action("TRIPLE_PRESS")
        self.assertTrue(overlay.dismissed)

    def test_force_send_on_double_press(self):
        """DOUBLE_PRESS during LISTENING triggers force_send."""
        overlay = self._make_overlay()
        mock_recorder = MagicMock()
        overlay._recorder = mock_recorder
        overlay.handle_action("DOUBLE_PRESS")
        mock_recorder.force_send.assert_called_once()

    def test_process_audio_transitions_to_thinking(self):
        """Processing audio transitions state to THINKING."""
        from overlays.blob_overlay import BlobOverlayState
        pipeline = FakeAudioPipeline()
        client = FakeClient(response_chunks=["Test response"])
        overlay = self._make_overlay(client=client, pipeline=pipeline)

        # Simulate the process_audio flow
        import io
        import wave
        import numpy as np

        # Create minimal WAV bytes
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(np.zeros(1600, dtype=np.int16).tobytes())
        wav_bytes = buf.getvalue()

        # Run _process_audio in a thread (it blocks on TTS)
        t = threading.Thread(target=overlay._process_audio, args=(wav_bytes,), daemon=True)
        t.start()
        t.join(timeout=5.0)

        # Should have progressed through THINKING → SPEAKING → DONE
        self.assertEqual(overlay._state, BlobOverlayState.DONE)
        self.assertTrue(pipeline.speak_called)

    def test_auto_dismiss_after_done_timeout(self):
        """Overlay auto-dismisses after DONE timeout."""
        from overlays.blob_overlay import BlobOverlayState
        overlay = self._make_overlay()
        overlay._state = BlobOverlayState.DONE
        overlay.auto_dismiss_ms = 100

        # Tick past the threshold
        overlay.tick(50)
        self.assertFalse(overlay.dismissed)
        overlay.tick(60)
        self.assertTrue(overlay.dismissed)

    def test_render_does_not_crash_in_any_state(self):
        """Render should not crash in any state."""
        from overlays.blob_overlay import BlobOverlayState
        overlay = self._make_overlay()

        for state in BlobOverlayState:
            overlay._state = state
            overlay._dismissed = False
            overlay.render(self.surface)  # Should not raise

    def test_on_dismiss_callback_fires(self):
        """on_dismiss callback fires when overlay is dismissed."""
        dismissed_calls = []
        overlay = self._make_overlay()
        overlay.on_dismiss = lambda: dismissed_calls.append(True)
        overlay._dismiss()
        self.assertEqual(len(dismissed_calls), 1)

    def test_error_handling_no_speech(self):
        """Overlay transitions to DONE with error when no transcript."""
        from overlays.blob_overlay import BlobOverlayState
        pipeline = FakeAudioPipeline()
        pipeline.transcribe_result = ""  # No speech detected
        client = FakeClient()
        overlay = self._make_overlay(client=client, pipeline=pipeline)

        # Create minimal WAV
        import io, wave
        import numpy as np
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(np.zeros(1600, dtype=np.int16).tobytes())

        overlay._process_audio(buf.getvalue())
        self.assertEqual(overlay._state, BlobOverlayState.DONE)
        self.assertEqual(overlay._error, "no speech")


# ══════════════════════════════════════════════════════════════════════
# 3. Navigate_to Tool → Device Screen Change
# ══════════════════════════════════════════════════════════════════════

class NavigateToToolTests(unittest.TestCase):
    """Test navigate_to agent tool and device-side handling."""

    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_navigate_to_tool_definition_exists(self):
        """navigate_to tool is defined in DEVICE_TOOLS."""
        from agent_tools import DEVICE_TOOLS
        names = [t["name"] for t in DEVICE_TOOLS]
        self.assertIn("navigate_to", names)

    def test_navigate_to_valid_target(self):
        """navigate_to with valid target produces a setting_change."""
        from agent_tools import handle_tool_call
        changes = []
        result = handle_tool_call(
            "navigate_to",
            {"target": "files"},
            device_settings={},
            setting_changes=changes,
        )
        parsed = json.loads(result)
        self.assertTrue(parsed.get("success"))
        self.assertEqual(parsed["target"], "files")
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["key"], "_navigate")
        self.assertEqual(changes[0]["value"], "files")

    def test_navigate_to_invalid_target(self):
        """navigate_to with invalid target returns error."""
        from agent_tools import handle_tool_call
        changes = []
        result = handle_tool_call(
            "navigate_to",
            {"target": "nonexistent"},
            device_settings={},
            setting_changes=changes,
        )
        parsed = json.loads(result)
        self.assertIn("error", parsed)
        self.assertEqual(len(changes), 0)

    def test_navigate_to_all_valid_targets(self):
        """All documented targets are accepted."""
        from agent_tools import handle_tool_call
        valid = [
            "home", "chat", "chat_new", "chat_history", "tasks",
            "settings", "focus", "mail", "messages", "files",
            "activity", "agent",
        ]
        for target in valid:
            changes = []
            result = handle_tool_call(
                "navigate_to",
                {"target": target},
                device_settings={},
                setting_changes=changes,
            )
            parsed = json.loads(result)
            self.assertTrue(parsed.get("success"), f"navigate_to({target}) failed: {parsed}")

    def test_client_on_navigate_callback(self):
        """BackendClient._apply_setting_change routes _navigate to on_navigate."""
        from client.api import BackendClient

        navigated_to = []
        client = BackendClient.__new__(BackendClient)
        client.on_navigate = lambda target: navigated_to.append(target)
        client.on_volume_change = None

        client._apply_setting_change({"key": "_navigate", "value": "tasks"})
        self.assertEqual(navigated_to, ["tasks"])

    def test_client_navigate_not_persisted(self):
        """_navigate setting is not persisted to repository."""
        from client.api import BackendClient

        client = BackendClient.__new__(BackendClient)
        client.on_navigate = lambda target: None
        client.on_volume_change = None

        # Should not attempt to persist — _navigate is a transient command
        # If it tried to persist, it would crash since we have no repo
        client._apply_setting_change({"key": "_navigate", "value": "chat"})
        # If we get here without exception, the _navigate key was handled
        # before hitting the persist code path


# ══════════════════════════════════════════════════════════════════════
# 4. Voice Recorder + SharedAudioStream Integration
# ══════════════════════════════════════════════════════════════════════

class VoiceRecorderIntegrationTests(unittest.TestCase):
    """Test VoiceRecorder with SharedAudioStream."""

    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_recorder_registers_on_start(self):
        """VoiceRecorder registers as consumer on SharedAudioStream."""
        stream = FakeSharedStream()
        from audio.voice_recorder import VoiceRecorder
        recorder = VoiceRecorder(shared_stream=stream)
        result = recorder.start()
        self.assertTrue(result)
        self.assertIn("voice_recorder", stream._consumers)
        recorder.stop()

    def test_recorder_unregisters_on_stop(self):
        """VoiceRecorder unregisters consumer on stop."""
        stream = FakeSharedStream()
        from audio.voice_recorder import VoiceRecorder
        recorder = VoiceRecorder(shared_stream=stream)
        recorder.start()
        recorder.stop()
        self.assertNotIn("voice_recorder", stream._consumers)

    def test_recorder_starts_stream_if_not_running(self):
        """VoiceRecorder starts the shared stream if not already running."""
        stream = FakeSharedStream()
        self.assertFalse(stream.is_running)
        from audio.voice_recorder import VoiceRecorder
        recorder = VoiceRecorder(shared_stream=stream)
        recorder.start()
        self.assertTrue(stream.is_running)
        recorder.stop()

    def test_force_send_ends_recording(self):
        """force_send() causes recorder to finish."""
        import numpy as np
        stream = FakeSharedStream()
        done_event = threading.Event()
        result_holder = [None]

        def on_done(wav_bytes):
            result_holder[0] = wav_bytes
            done_event.set()

        from audio.voice_recorder import VoiceRecorder
        recorder = VoiceRecorder(
            shared_stream=stream,
            on_done=on_done,
            silence_timeout=10.0,
            max_duration=30.0,
        )
        recorder.start()

        # Feed some speech-like frames
        buf = stream._consumers.get("voice_recorder")
        if buf is not None:
            for _ in range(20):
                frame = (np.random.randn(512) * 5000).astype(np.int16)
                buf.append(frame)

        time.sleep(0.1)
        recorder.force_send()
        done_event.wait(timeout=5.0)
        self.assertTrue(done_event.is_set())


if __name__ == "__main__":
    unittest.main()
