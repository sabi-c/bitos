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
    SAMPLE_RATE = 16000
    CHANNELS = 1
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
                    str(self.SAMPLE_RATE),
                    "-c",
                    str(self.CHANNELS),
                    out,
                ]
            )
            self._rec_proc = proc
            return out
        except Exception as e:
            logger.error("record_failed error=%s", e)
            return None

    def stop_recording(self) -> None:
        if self._rec_proc:
            self._rec_proc.terminate()
            self._rec_proc.wait(timeout=2)
            self._rec_proc = None

    def transcribe(self, audio_path: str) -> str:
        """Send to Whisper API. Falls back to empty string."""
        try:
            import openai

            client = openai.OpenAI(api_key=os.environ.get("ANTHROPIC_API_KEY"))
            with open(audio_path, "rb") as f:
                result = client.audio.transcriptions.create(model="whisper-1", file=f)
            return result.text
        except Exception as e:
            logger.error("transcribe_failed error=%s", e)
            return ""
        finally:
            if os.path.exists(audio_path):
                os.remove(audio_path)

    def speak(self, text: str) -> None:
        """TTS via OpenAI, play via aplay. Falls back to Piper."""
        try:
            self._speak_openai(text)
        except Exception:
            self._speak_piper(text)

    def _speak_openai(self, text: str) -> None:
        import openai

        client = openai.OpenAI(api_key=os.environ.get("ANTHROPIC_API_KEY"))
        out = "/tmp/bitos_tts.mp3"
        with client.audio.speech.with_streaming_response.create(model="tts-1", voice="alloy", input=text) as resp:
            resp.stream_to_file(out)
        self._play_audio(out, timeout=30)

    def _speak_piper(self, text: str) -> None:
        model = os.environ.get("PIPER_MODEL", "/home/pi/bitos/models/tts/en_US-lessac-medium.onnx")
        if not os.path.exists(model):
            logger.warning("piper_model_missing path=%s", model)
            return
        out = "/tmp/bitos_tts.wav"
        subprocess.run(
            ["piper", "--model", model, "--output_file", out],
            input=text.encode(),
            capture_output=True,
            timeout=30,
            check=False,
        )
        self._play_audio(out, timeout=10)

    def _play_audio(self, path: str, timeout: int) -> None:
        self._speak_proc = subprocess.Popen(
            ["aplay", "-D", self.ALSA_DEVICE, path],
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
    if mode == "mock":
        return MockAudioPipeline()
    return MockAudioPipeline()
