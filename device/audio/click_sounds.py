"""Programmatic click-sound feedback for button presses.

Generates tiny sine-burst sounds in memory (no WAV files needed).
Uses pygame.mixer.Sound for non-blocking playback at low volume.
"""

from __future__ import annotations

import logging
import math
import struct

logger = logging.getLogger(__name__)

# Sample rate and format for generated sounds
_SAMPLE_RATE = 44100
_MAX_AMPLITUDE = 16000  # int16 range, kept moderate


def _generate_tone(freq: float, duration_ms: float, fade_ms: float = 1.0) -> bytes:
    """Generate a short sine-burst as signed-16-bit mono PCM bytes."""
    n_samples = int(_SAMPLE_RATE * duration_ms / 1000.0)
    n_fade = int(_SAMPLE_RATE * fade_ms / 1000.0)
    samples = []
    for i in range(n_samples):
        t = i / _SAMPLE_RATE
        val = math.sin(2.0 * math.pi * freq * t) * _MAX_AMPLITUDE
        # Fade in/out to avoid clicks
        if i < n_fade:
            val *= i / max(n_fade, 1)
        elif i > n_samples - n_fade:
            val *= (n_samples - i) / max(n_fade, 1)
        samples.append(int(val))
    return struct.pack(f"<{len(samples)}h", *samples)


def _generate_ascending(freqs: list[float], step_ms: float = 15.0) -> bytes:
    """Generate ascending tone sequence (for confirm sound)."""
    parts = []
    for freq in freqs:
        parts.append(_generate_tone(freq, step_ms, fade_ms=1.0))
    return b"".join(parts)


class ClickSoundPlayer:
    """Pre-generated click sounds played via pygame.mixer.Sound."""

    def __init__(self, volume: float = 0.12, enabled: bool = True):
        self._volume = max(0.0, min(1.0, volume))
        self._enabled = enabled
        self._sounds: dict[str, object] = {}
        self._initialized = False

    def _ensure_init(self) -> bool:
        """Lazily initialize sounds after pygame.mixer is ready."""
        if self._initialized:
            return True
        try:
            import pygame

            if not pygame.mixer.get_init():
                return False
            # Soft click: 2ms sine burst at 1200 Hz
            tap_data = _generate_tone(1200, 2.0, fade_ms=0.5)
            # Deep click: 5ms at 600 Hz
            back_data = _generate_tone(600, 5.0, fade_ms=1.0)
            # Confirm: short ascending 800 -> 1200 Hz
            confirm_data = _generate_ascending([800, 1200], step_ms=15.0)
            # Error: descending 600 -> 300 Hz
            error_data = _generate_ascending([600, 300], step_ms=25.0)

            for name, pcm in [
                ("tap", tap_data),
                ("back", back_data),
                ("confirm", confirm_data),
                ("error", error_data),
            ]:
                snd = pygame.mixer.Sound(buffer=pcm)
                snd.set_volume(self._volume)
                self._sounds[name] = snd

            self._initialized = True
            logger.info("click_sounds_init: %d sounds loaded vol=%.0f%%",
                        len(self._sounds), self._volume * 100)
            return True
        except Exception as exc:
            logger.debug("click_sounds_init_failed: %s", exc)
            return False

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, volume))
        for snd in self._sounds.values():
            snd.set_volume(self._volume)

    def _play(self, name: str) -> None:
        if not self._enabled:
            return
        if not self._ensure_init():
            return
        snd = self._sounds.get(name)
        if snd is not None:
            try:
                snd.play()
            except Exception as exc:
                logger.debug("click_play_failed: name=%s error=%s", name, exc)

    def play_tap(self) -> None:
        """Soft click for SHORT_PRESS / navigation."""
        self._play("tap")

    def play_confirm(self) -> None:
        """Ascending tone for DOUBLE_PRESS / select."""
        self._play("confirm")

    def play_back(self) -> None:
        """Deep click for LONG_PRESS / back."""
        self._play("back")

    def play_error(self) -> None:
        """Descending tone for error states."""
        self._play("error")
