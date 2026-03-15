import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "device"))

from audio.pipeline import AudioPipeline
from client.api import BackendChatError
from screens.panels.chat import ChatPanel


class _StubAudioPipeline(AudioPipeline):
    def __init__(self, transcript: str = "", speaking_delay: float = 0.0):
        self.transcript = transcript
        self.record_called_with = None
        self.recording_stopped = False
        self._speaking = False
        self.speaking_delay = speaking_delay
        self.stop_speaking_called = False

    def record(self, max_seconds: int = 60) -> str | None:
        self.record_called_with = max_seconds
        return "/tmp/fake.wav"

    def stop_recording(self) -> None:
        self.recording_stopped = True

    def transcribe(self, audio_path: str) -> str:
        return self.transcript

    def speak(self, text: str) -> None:
        self._speaking = True
        time.sleep(self.speaking_delay)
        self._speaking = False

    def is_speaking(self) -> bool:
        return self._speaking

    def stop_speaking(self) -> None:
        self.stop_speaking_called = True
        self._speaking = False


class _StreamingErrorClient:
    def chat(self, _message):
        raise BackendChatError("offline", "down", retryable=True)


class _SpeakClient:
    def chat(self, _message):
        return iter(["hello world"])


class VoiceHardeningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()
        pygame.font.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_empty_transcription_shows_error_and_skips_send(self):
        panel = ChatPanel(_SpeakClient(), audio_pipeline=_StubAudioPipeline(transcript="   "))
        with patch("time.sleep", return_value=None):
            panel._do_voice_capture()

        self.assertEqual(panel._status_detail, "Didn't catch that — try again")
        self.assertEqual(panel._messages, [])

    def test_record_timeout_fires_after_30_seconds(self):
        audio = _StubAudioPipeline(transcript="hello")
        panel = ChatPanel(_SpeakClient(), audio_pipeline=audio)
        panel._send_message = lambda: None
        with patch("time.sleep", return_value=None):
            panel._do_voice_capture()

        self.assertEqual(audio.record_called_with, 30)
        self.assertTrue(audio.recording_stopped)
        self.assertIn("Recording stopped (30s max)", panel._status_detail)

    def test_speaking_indicator_set_during_tts(self):
        audio = _StubAudioPipeline(transcript="", speaking_delay=0.1)
        panel = ChatPanel(_SpeakClient(), audio_pipeline=audio)

        thread = threading.Thread(target=panel._stream_response, args=("hello",), daemon=True)
        thread.start()
        time.sleep(0.02)

        self.assertEqual(panel._status_detail, "◎ SPEAKING...")
        thread.join(timeout=1)

    def test_stop_speaking_cancels_playback(self):
        audio = _StubAudioPipeline(speaking_delay=0.5)
        panel = ChatPanel(_SpeakClient(), audio_pipeline=audio)

        thread = threading.Thread(target=panel._stream_response, args=("hello",), daemon=True)
        thread.start()
        time.sleep(0.05)

        panel.handle_action("SHORT_PRESS")

        self.assertTrue(audio.stop_speaking_called)
        thread.join(timeout=1)

    def test_server_error_preserves_input_text(self):
        panel = ChatPanel(_StreamingErrorClient())
        panel._input_text = "retry me"
        panel._send_message()

        for _ in range(100):
            if not panel._is_streaming:
                break
            pygame.time.wait(5)

        self.assertEqual(panel._status_detail, "Server offline")
        self.assertEqual(panel._input_text, "retry me")


if __name__ == "__main__":
    unittest.main()
