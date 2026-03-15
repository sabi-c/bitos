"""Piper-based text-to-speech speaker."""

from __future__ import annotations

import io
import logging
import os
import threading
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd
from piper import PiperVoice

logger = logging.getLogger(__name__)


class Speaker:
    def __init__(self, voice_model: str = "assets/voices/en_US-ryan-low.onnx") -> None:
        self._voice_model = Path(voice_model)
        self._voice: PiperVoice | None = None

    def _load_voice(self) -> PiperVoice | None:
        if self._voice is not None:
            return self._voice

        model_path = self._voice_model
        if not model_path.is_absolute():
            model_path = Path(os.getcwd()) / model_path

        if not model_path.exists():
            logger.error("piper_model_missing path=%s", model_path)
            return None

        self._voice = PiperVoice.load(str(model_path))
        return self._voice

    def speak(self, text: str) -> None:
        if not text:
            return
        voice = self._load_voice()
        if voice is None:
            return

        wav_buf = io.BytesIO()
        with wave.open(wav_buf, "wb") as wav_file:
            voice.synthesize(text, wav_file)

        with wave.open(io.BytesIO(wav_buf.getvalue()), "rb") as wav_in:
            frames = wav_in.readframes(wav_in.getnframes())
            sample_rate = wav_in.getframerate()
            channels = wav_in.getnchannels()

        audio = np.frombuffer(frames, dtype=np.int16)
        if channels > 1:
            audio = audio.reshape(-1, channels)

        sd.play(audio, sample_rate)
        sd.wait()

    def speak_async(self, text: str) -> threading.Thread:
        thread = threading.Thread(target=self.speak, args=(text,), daemon=True)
        thread.start()
        return thread
