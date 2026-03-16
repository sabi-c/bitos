"""TTS helpers with runtime fallback chain: piper -> openai -> espeak -> silent."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np

from .player import AudioPlayer


logger = logging.getLogger(__name__)

SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", os.getenv("ALSA_SAMPLE_RATE", "48000")))
CHANNELS = int(os.getenv("AUDIO_CHANNELS", "2"))
PLAYBACK_DEVICE = os.getenv("ALSA_PLAYBACK_DEVICE", "default")


class TextToSpeech:
    def __init__(self, player: AudioPlayer | None = None):
        self.player = player or AudioPlayer()
        # Apply persisted volume setting
        try:
            from storage.repository import DeviceRepository
            repo = DeviceRepository()
            vol = repo.get_setting("volume", 100)
            self.player.set_volume(max(0, min(100, int(vol))) / 100.0)
        except Exception:
            pass
        self.engine = self._detect_engine()
        logger.info("tts_engine=%s", self.engine)

    def _detect_engine(self) -> str:
        # Check if user has forced a specific engine in settings
        preferred = None
        try:
            from storage.repository import DeviceRepository
            repo = DeviceRepository()
            preferred = str(repo.get_setting("tts_engine", "auto") or "auto").lower()
        except Exception:
            pass

        has_speechify = bool(os.environ.get("SPEECHIFY_API_KEY"))
        has_openai_key = bool(os.environ.get("OPENAI_API_KEY"))
        has_piper = shutil.which("piper") and os.path.exists(
            os.getenv("PIPER_MODEL", "/home/pi/bitos/models/tts/en_US-lessac-medium.onnx")
        )
        has_espeak = shutil.which("espeak") or shutil.which("espeak-ng")
        logger.info("tts_detect: preferred=%s speechify=%s piper=%s openai=%s espeak=%s",
                     preferred, has_speechify, bool(has_piper), has_openai_key, bool(has_espeak))

        # If user picked a specific engine and it's available, use it
        if preferred and preferred != "auto":
            if preferred == "speechify" and has_speechify:
                return "speechify"
            if preferred == "piper" and has_piper:
                return "piper"
            if preferred == "openai" and has_openai_key:
                return "openai"
            if preferred == "espeak" and has_espeak:
                return "espeak"
            logger.warning("tts_preferred=%s not available, falling back to auto", preferred)

        # Auto: best available
        if has_speechify:
            return "speechify"
        if has_piper:
            return "piper"
        if has_openai_key:
            return "openai"
        if has_espeak:
            return "espeak"
        return "silent"

    def speak(self, text: str) -> bool:
        if not text.strip():
            return False
        if self.engine == "silent":
            logger.warning("tts_engine=silent; skipping synthesis")
            return False

        logger.info("tts_speak: engine=%s text_len=%d text_preview='%s'",
                     self.engine, len(text), text[:60].replace('\n', ' '))
        out = Path(tempfile.mkstemp(prefix="bitos_tts_", suffix=".wav")[1])
        try:
            if self.engine == "speechify":
                self._run_speechify(text, out)
            elif self.engine == "piper":
                self._run_piper(text, out)
            elif self.engine == "openai":
                self._run_openai_tts(text, out)
            elif self.engine == "espeak":
                self._run_espeak(text, out)
            if not out.exists() or out.stat().st_size == 0:
                logger.warning("tts_speak: output file empty or missing after synthesis")
                return False
            size = out.stat().st_size
            logger.info("tts_speak: synthesized %d bytes", size)
            # Only resample if using pygame (desktop); aplay reads WAV headers natively
            from .player import _USE_APLAY
            if not _USE_APLAY:
                self._ensure_48k_stereo_wav(out)
                logger.info("tts_speak: resampled to 48k stereo, %d bytes", out.stat().st_size)
            logger.info("tts_speak: playing audio")
            return self.player.play_file(str(out))
        finally:
            if out.exists():
                out.unlink(missing_ok=True)

    def _run_speechify(self, text: str, output_file: Path) -> None:
        from .speechify import synthesize
        if not synthesize(text, output_file):
            # Fallback to next available engine
            logger.warning("speechify_fallback: trying next engine")
            for fallback in ("piper", "openai", "espeak"):
                if fallback == "piper" and shutil.which("piper"):
                    self._run_piper(text, output_file)
                    return
                if fallback == "openai" and os.environ.get("OPENAI_API_KEY"):
                    self._run_openai_tts(text, output_file)
                    return
                if fallback == "espeak" and (shutil.which("espeak") or shutil.which("espeak-ng")):
                    self._run_espeak(text, output_file)
                    return

    def _run_piper(self, text: str, output_file: Path) -> None:
        model = os.getenv("PIPER_MODEL", "/home/pi/bitos/models/tts/en_US-lessac-medium.onnx")
        env = os.environ.copy()
        env["ALSA_DEFAULT_PCM"] = PLAYBACK_DEVICE
        subprocess.run(
            ["piper", "--model", model, "--output_file", str(output_file)],
            input=text.encode("utf-8"),
            check=False,
            timeout=30,
            env=env,
        )


    def _run_openai_tts(self, text: str, output_file: Path) -> None:
        import openai

        client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        with client.audio.speech.with_streaming_response.create(
            model="tts-1", voice="alloy", input=text
        ) as resp:
            resp.stream_to_file(str(output_file))

    def _run_espeak(self, text: str, output_file: Path) -> None:
        espeak_cmd = shutil.which("espeak-ng") or shutil.which("espeak")
        if not espeak_cmd:
            return
        env = os.environ.copy()
        env["ALSA_DEFAULT_PCM"] = PLAYBACK_DEVICE
        subprocess.run([espeak_cmd, "-v", "en-us", "-s", "150", "-w", str(output_file), text], check=False, timeout=20, env=env)

    def _ensure_48k_stereo_wav(self, path: Path) -> None:
        with wave.open(str(path), "rb") as src:
            in_channels = src.getnchannels()
            in_rate = src.getframerate()
            sample_width = src.getsampwidth()
            frames = src.readframes(src.getnframes())

        if sample_width != 2:
            return

        if in_rate == SAMPLE_RATE and in_channels == 2:
            return

        audio = np.frombuffer(frames, dtype=np.int16)
        if in_channels == 2:
            stereo = audio.reshape(-1, 2)
        else:
            mono = audio.reshape(-1, 1)
            stereo = np.repeat(mono, 2, axis=1)

        if in_rate != SAMPLE_RATE and len(stereo) > 1:
            old_idx = np.linspace(0.0, 1.0, num=len(stereo), endpoint=True)
            new_len = int(round(len(stereo) * SAMPLE_RATE / in_rate))
            new_idx = np.linspace(0.0, 1.0, num=max(1, new_len), endpoint=True)
            left = np.interp(new_idx, old_idx, stereo[:, 0]).astype(np.int16)
            right = np.interp(new_idx, old_idx, stereo[:, 1]).astype(np.int16)
            stereo = np.column_stack((left, right))

        with wave.open(str(path), "wb") as dst:
            dst.setnchannels(CHANNELS)
            dst.setsampwidth(2)
            dst.setframerate(SAMPLE_RATE)
            dst.writeframes(stereo.astype(np.int16).tobytes())
