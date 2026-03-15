"""Audio playback helpers for WM8960 (card 0, device 0)."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np
import pygame


logger = logging.getLogger(__name__)

PLAYBACK_DEVICE = os.getenv("ALSA_PLAYBACK_DEVICE", "hw:0,0")
SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", os.getenv("ALSA_SAMPLE_RATE", "48000")))
CHANNELS = int(os.getenv("AUDIO_CHANNELS", "2"))


class AudioPlayer:
    def __init__(self, volume: float = 1.0):
        self._volume = max(0.0, min(1.0, volume))
        self._initialized = False

    def _init(self) -> None:
        if self._initialized:
            return
        os.environ.setdefault("AUDIODEV", PLAYBACK_DEVICE)
        pygame.mixer.pre_init(SAMPLE_RATE, -16, CHANNELS, 4096)
        pygame.mixer.init()
        pygame.mixer.music.set_volume(self._volume)
        self._initialized = True
        logger.info("playback_device=%s sample_rate=%s channels=%s", PLAYBACK_DEVICE, SAMPLE_RATE, CHANNELS)

    def ensure_stereo_16bit(self, audio_data: bytes, channels: int = 1) -> bytes:
        """Return int16 little-endian PCM audio bytes in stereo format."""
        if channels == 2:
            return audio_data
        mono = np.frombuffer(audio_data, dtype=np.int16)
        stereo = np.column_stack([mono, mono]).flatten()
        return stereo.tobytes()

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, volume))
        if self._initialized:
            pygame.mixer.music.set_volume(self._volume)

    def play_file(self, path: str) -> bool:
        audio = Path(path)
        if not audio.exists():
            logger.error("audio_file_missing path=%s", path)
            return False
        self._init()
        try:
            pygame.mixer.music.load(str(audio))
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.wait(50)
            return True
        finally:
            self.release()

    def release(self) -> None:
        if self._initialized:
            try:
                pygame.mixer.music.stop()
                pygame.mixer.quit()
            finally:
                self._initialized = False
