"""BITOS audio pipelines for mock desktop and Pi WM8960 hardware."""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile
import time
from pathlib import Path


logger = logging.getLogger(__name__)


class AudioPipeline:
    """Audio recording, STT, and TTS pipeline interface."""

    def record(self, max_seconds: int = 60) -> str | None:
        raise NotImplementedError

    def stop_recording(self) -> None:
        return None

    def transcribe(self, audio_path: str) -> str:
        raise NotImplementedError

    def speak(self, text: str) -> None:
        raise NotImplementedError

    def is_speaking(self) -> bool:
        return False

    def stop_speaking(self) -> None:
        return None

    def is_available(self) -> bool:
        return False


class MockAudioPipeline(AudioPipeline):
    """Desktop-safe mock pipeline for local development and tests."""

    def __init__(self):
        self._last_typed_text = ""
        self._speaking = False

    def record(self, max_seconds: int = 60) -> str | None:
        fd, out = tempfile.mkstemp(prefix="bitos_mock_rec_", suffix=".txt")
        os.close(fd)
        Path(out).write_text("", encoding="utf-8")
        return out

    def transcribe(self, audio_path: str) -> str:
        try:
            typed = Path(audio_path).read_text(encoding="utf-8") if audio_path else ""
            self._last_typed_text = typed
            return typed
        except Exception:
            return self._last_typed_text
        finally:
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)

    def speak(self, text: str) -> None:
        self._speaking = True
        try:
            logger.info("mock_speak text_len=%s", len(text))
        finally:
            self._speaking = False

    def is_speaking(self) -> bool:
        return self._speaking

    def stop_speaking(self) -> None:
        self._speaking = False

    def is_available(self) -> bool:
        return True


class WM8960Pipeline(AudioPipeline):
    """
    # WHY THIS EXISTS: real audio for Whisplay HAT WM8960.
    # Only instantiated when BITOS_AUDIO=hw:0 on Pi hardware.
    # Reference: github.com/PiSugar/whisplay-ai-chatbot
    """

    ALSA_DEVICE = os.environ.get("BITOS_AUDIO", "hw:0")
    # STT-optimized: 16kHz mono matches Whisper's native format
    RECORD_SAMPLE_RATE = 16000
    RECORD_CHANNELS = 1
    # Playback stays at 48kHz stereo for WM8960 speaker output
    PLAYBACK_SAMPLE_RATE = 48000
    PLAYBACK_CHANNELS = 2
    FORMAT = "S16_LE"
    CHUNK_SECONDS = 0.1

    def __init__(self):
        self._rec_proc: subprocess.Popen | None = None
        self._speak_proc: subprocess.Popen | None = None

    def record(self, max_seconds: int = 60) -> str | None:
        """Record until button released or max_seconds."""
        out = f"/tmp/bitos_rec_{int(time.time())}.wav"
        try:
            proc = subprocess.Popen(
                [
                    "arecord",
                    "-D",
                    self.ALSA_DEVICE,
                    "-f",
                    self.FORMAT,
                    "-r",
                    str(self.RECORD_SAMPLE_RATE),
                    "-c",
                    str(self.RECORD_CHANNELS),
                    "-d",
                    str(max_seconds),
                    out,
                ],
                stderr=subprocess.PIPE,
            )
            self._rec_proc = proc
            return out
        except Exception as e:
            logger.error("record_failed error=%s", e)
            return None

    def stop_recording(self) -> None:
        if self._rec_proc:
            try:
                self._rec_proc.terminate()
                self._rec_proc.wait(timeout=3)
                # Read any stderr from arecord for diagnostics
                if self._rec_proc.stderr:
                    err = self._rec_proc.stderr.read()
                    if err:
                        logger.info("arecord_stderr: %s", err.decode(errors="replace").strip())
            except subprocess.TimeoutExpired:
                self._rec_proc.kill()
                self._rec_proc.wait(timeout=1)
                logger.warning("arecord_killed after timeout")
            finally:
                self._rec_proc = None

    def transcribe(self, audio_path: str) -> str:
        from audio.stt import SpeechToText

        return SpeechToText().transcribe(audio_path)

    def speak(self, text: str) -> None:
        from audio.player import AudioPlayer
        from audio.tts import TextToSpeech

        TextToSpeech(AudioPlayer()).speak(text)

    def _play_audio(self, path: str, timeout: int) -> None:
        self._speak_proc = subprocess.Popen(
            [
                "aplay",
                "-D",
                self.ALSA_DEVICE,
                "-f",
                self.FORMAT,
                "-r",
                str(self.PLAYBACK_SAMPLE_RATE),
                "-c",
                str(self.PLAYBACK_CHANNELS),
                path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            self._speak_proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self.stop_speaking()
        finally:
            self._speak_proc = None

    def is_speaking(self) -> bool:
        return self._speak_proc is not None and self._speak_proc.poll() is None

    def stop_speaking(self) -> None:
        if self._speak_proc and self._speak_proc.poll() is None:
            self._speak_proc.terminate()
            try:
                self._speak_proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._speak_proc.kill()

    def is_available(self) -> bool:
        return True


def get_audio_pipeline() -> AudioPipeline:
    mode = os.environ.get("BITOS_AUDIO", "mock").lower()
    if mode == "hw:0" or mode.startswith("hw:"):
        return WM8960Pipeline()
    return MockAudioPipeline()
