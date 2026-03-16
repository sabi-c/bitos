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
    Real audio for Whisplay HAT WM8960 on Pi Zero 2W.
    Uses sox for recording — handles stereo→mono downmix automatically.
    WM8960 only supports stereo capture; sox -c 1 mixes down to mono.
    Reference: github.com/PiSugar/whisplay-ai-chatbot
    """

    ALSA_DEVICE = os.environ.get("BITOS_AUDIO", "hw:0")
    RECORD_SAMPLE_RATE = 16000
    # Playback stays at 48kHz stereo for WM8960 speaker output
    PLAYBACK_SAMPLE_RATE = 48000
    PLAYBACK_CHANNELS = 2
    FORMAT = "S16_LE"

    def __init__(self):
        self._rec_proc: subprocess.Popen | None = None
        self._speak_proc: subprocess.Popen | None = None
        self._rec_path: str | None = None

    def record(self, max_seconds: int = 60) -> str | None:
        """Record until button released or max_seconds.

        WM8960 only supports stereo capture — we record stereo then
        convert to mono 16kHz WAV for Whisper STT in stop_recording().
        """
        # Record stereo; will be converted to mono on stop
        out = f"/tmp/bitos_rec_{int(time.time())}.wav"
        self._rec_path = out
        try:
            cmd = [
                "arecord",
                "-D", self.ALSA_DEVICE,
                "-f", self.FORMAT,
                "-r", str(self.RECORD_SAMPLE_RATE),
                "-c", "2",  # WM8960 requires stereo
                "-d", str(max_seconds),
                out,
            ]
            logger.info("record_start cmd=%s", " ".join(cmd))
            proc = subprocess.Popen(cmd, stderr=subprocess.PIPE)
            self._rec_proc = proc

            # Verify the process didn't die immediately (bad device, etc.)
            time.sleep(0.3)
            if proc.poll() is not None:
                stderr = proc.stderr.read().decode(errors="replace").strip() if proc.stderr else ""
                logger.error("record_died_immediately rc=%d stderr=%s", proc.returncode, stderr[:120])
                self._rec_proc = None
                return None

            return out
        except Exception as e:
            logger.error("record_failed error=%s", e)
            return None

    def stop_recording(self) -> None:
        if self._rec_proc:
            try:
                self._rec_proc.terminate()
                self._rec_proc.wait(timeout=3)
                if self._rec_proc.stderr:
                    err = self._rec_proc.stderr.read()
                    if err:
                        logger.info("record_stderr: %s", err.decode(errors="replace").strip())
            except subprocess.TimeoutExpired:
                self._rec_proc.kill()
                self._rec_proc.wait(timeout=1)
                logger.warning("record_killed after timeout")
            finally:
                self._rec_proc = None

        # Convert stereo WAV → mono for Whisper STT
        if self._rec_path and os.path.exists(self._rec_path):
            self._convert_to_mono(self._rec_path)

    @staticmethod
    def _convert_to_mono(wav_path: str) -> None:
        """Convert stereo WAV to mono in-place using Python's wave module."""
        import struct
        import wave

        try:
            with wave.open(wav_path, "rb") as wf:
                channels = wf.getnchannels()
                if channels == 1:
                    return  # Already mono
                sampwidth = wf.getsampwidth()
                framerate = wf.getframerate()
                frames = wf.readframes(wf.getnframes())

            # Average left+right channels → mono
            if sampwidth == 2:  # S16_LE
                samples = struct.unpack(f"<{len(frames) // 2}h", frames)
                mono = []
                for i in range(0, len(samples), channels):
                    avg = sum(samples[i:i + channels]) // channels
                    mono.append(avg)
                mono_bytes = struct.pack(f"<{len(mono)}h", *mono)
            else:
                logger.warning("stereo_to_mono: unsupported sampwidth=%d", sampwidth)
                return

            mono_path = wav_path
            with wave.open(mono_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(sampwidth)
                wf.setframerate(framerate)
                wf.writeframes(mono_bytes)

            logger.info("stereo_to_mono: converted %s (%d ch → 1)", wav_path, channels)
        except Exception as exc:
            logger.error("stereo_to_mono_failed: %s", exc)

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
    mode = os.environ.get("BITOS_AUDIO", "mock").strip().lower()
    if not mode or mode == "mock":
        return MockAudioPipeline()
    # Any hw: or "default" device → real pipeline
    return WM8960Pipeline()
