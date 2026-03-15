"""TTS helpers with runtime fallback chain: piper -> espeak -> silent."""

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
PLAYBACK_DEVICE = os.getenv("ALSA_PLAYBACK_DEVICE", "hw:0,0")


class TextToSpeech:
    def __init__(self, player: AudioPlayer | None = None):
        self.player = player or AudioPlayer()
        self.engine = self._detect_engine()
        logger.info("tts_engine=%s", self.engine)

    def _detect_engine(self) -> str:
        has_piper = shutil.which("piper")
        has_espeak = shutil.which("espeak") or shutil.which("espeak-ng")
        if has_piper:
            return "piper"
        if has_espeak:
            return "espeak"
        return "silent"

    def speak(self, text: str) -> bool:
        if not text.strip():
            return False
        if self.engine == "silent":
            logger.warning("tts_engine=silent; skipping synthesis")
            return False

        out = Path(tempfile.mkstemp(prefix="bitos_tts_", suffix=".wav")[1])
        try:
            if self.engine == "piper":
                self._run_piper(text, out)
            elif self.engine == "espeak":
                self._run_espeak(text, out)
            if not out.exists() or out.stat().st_size == 0:
                return False
            self._ensure_48k_stereo_wav(out)
            return self.player.play_file(str(out))
        finally:
            if out.exists():
                out.unlink(missing_ok=True)

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
