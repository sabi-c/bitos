"""Piper-based text-to-speech speaker (with safe fallbacks).

STATUS: Deprecated — superseded by audio.tts.TextToSpeech which is used by
audio.pipeline (the main audio path). This module is only referenced by
VoicePipeline, which is itself unused. Kept until VoicePipeline's future is decided.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import sounddevice as sd
    import numpy as np
    _SD_AVAILABLE = True
except ImportError:
    _SD_AVAILABLE = False
    logger.warning("sounddevice not available — speaker disabled")

try:
    from piper import PiperVoice
    _PIPER_AVAILABLE = True
except ImportError:
    _PIPER_AVAILABLE = False
    logger.warning("piper not available — TTS disabled")

VOICE_MODEL = "assets/voices/en_US-ryan-low.onnx"


class Speaker:
    def __init__(self, model_path: str = VOICE_MODEL, voice_model: str = None) -> None:
        if voice_model:
            model_path = voice_model
        self._voice_model = Path(model_path)
        self._voice = None

    def speak(self, text: str) -> None:
        if not text:
            return
        if not _PIPER_AVAILABLE or not _SD_AVAILABLE:
            logger.info("speak (TTS unavailable): %s", text[:80])
            return
        import io, wave
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

    def _load_voice(self):
        if self._voice is not None:
            return self._voice
        if not _PIPER_AVAILABLE:
            return None
        import os
        model_path = self._voice_model
        if not model_path.is_absolute():
            model_path = Path(os.getcwd()) / model_path
        if not model_path.exists():
            logger.error("piper_model_missing path=%s", model_path)
            return None
        self._voice = PiperVoice.load(str(model_path))
        return self._voice

    def speak_async(self, text: str) -> threading.Thread:
        thread = threading.Thread(target=self.speak, args=(text,), daemon=True)
        thread.start()
        return thread
