"""Audio playback helpers for WM8960 (card 0, device 0).

Uses aplay (ALSA) on Pi hardware, pygame.mixer as fallback for desktop.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

PLAYBACK_DEVICE = os.getenv("ALSA_PLAYBACK_DEVICE", "default")
SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", os.getenv("ALSA_SAMPLE_RATE", "48000")))
CHANNELS = int(os.getenv("AUDIO_CHANNELS", "2"))

# Use aplay on Pi (real ALSA device), pygame on desktop
_USE_APLAY = os.getenv("BITOS_AUDIO", "").strip().lower() not in ("", "mock")


_alsa_initialized = False


def init_alsa_soft_start(target_pct: int = 100) -> None:
    """Initialize ALSA speaker with soft-start to prevent WM8960 pop/click.

    Call once at boot before any audio playback. Ramps volume from 0%
    to target over ~200ms to let the codec DC-couple smoothly.
    """
    global _alsa_initialized
    if _alsa_initialized or not _USE_APLAY:
        return

    import time

    try:
        # Start at 0% — prevents the initial pop
        subprocess.run(
            ["amixer", "sset", "Speaker", "0%"],
            capture_output=True, timeout=3,
        )
        time.sleep(0.05)

        # Ramp in 4 steps over ~200ms
        for step_pct in (10, 30, 60, target_pct):
            subprocess.run(
                ["amixer", "sset", "Speaker", f"{min(step_pct, target_pct)}%"],
                capture_output=True, timeout=3,
            )
            time.sleep(0.05)

        _alsa_initialized = True
        logger.info("alsa_soft_start: ramped to %d%%", target_pct)
    except Exception as exc:
        logger.warning("alsa_soft_start_failed: %s", exc)
        _alsa_initialized = True  # Don't retry


class AudioPlayer:
    def __init__(self, volume: float = 1.0):
        self._volume = max(0.0, min(1.0, volume))
        self._proc: subprocess.Popen | None = None
        self._stopped = False  # flag for immediate cancellation

    def set_volume(self, volume: float) -> None:
        self._volume = max(0.0, min(1.0, volume))
        if _USE_APLAY:
            # Ensure soft-start has run before any volume change
            init_alsa_soft_start(int(self._volume * 100))
            pct = int(self._volume * 100)
            try:
                subprocess.run(
                    ["amixer", "sset", "Speaker", f"{pct}%"],
                    capture_output=True, timeout=3,
                )
                logger.info("alsa_volume_set=%d%%", pct)
            except Exception as exc:
                logger.warning("alsa_volume_set_failed: %s", exc)

    def play_file(self, path: str) -> bool:
        audio = Path(path)
        if not audio.exists():
            logger.error("audio_file_missing path=%s", path)
            return False

        self._stopped = False
        if _USE_APLAY:
            return self._play_aplay(str(audio))
        return self._play_pygame(str(audio))

    def _play_aplay(self, path: str) -> bool:
        """Play WAV file via ALSA aplay (thread-safe, no pygame conflict)."""
        cmd = [
            "aplay",
            "-D", PLAYBACK_DEVICE,
            path,
        ]
        logger.info("aplay_start: device=%s path=%s", PLAYBACK_DEVICE, path)
        try:
            self._proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
            )
            _, stderr = self._proc.communicate(timeout=60)
            rc = self._proc.returncode
            if rc != 0:
                err = stderr.decode(errors="replace").strip()[:120] if stderr else ""
                logger.error("aplay_failed: rc=%d stderr=%s", rc, err)
                return False
            logger.info("aplay_done: path=%s", path)
            return True
        except subprocess.TimeoutExpired:
            self.stop()
            logger.error("aplay_timeout: path=%s", path)
            return False
        except Exception as exc:
            logger.error("aplay_error: %s", exc)
            return False
        finally:
            self._proc = None

    def _play_pygame(self, path: str) -> bool:
        """Play WAV file via pygame.mixer (desktop fallback)."""
        import pygame

        try:
            if not pygame.mixer.get_init():
                os.environ["AUDIODEV"] = PLAYBACK_DEVICE
                pygame.mixer.pre_init(SAMPLE_RATE, -16, CHANNELS, 4096)
                pygame.mixer.init()
            pygame.mixer.music.set_volume(self._volume)
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                if self._stopped:
                    pygame.mixer.music.stop()
                    logger.info("pygame_play_stopped: path=%s", path)
                    return False
                pygame.time.wait(50)
            logger.info("pygame_play_done: path=%s", path)
            return True
        except Exception as exc:
            logger.error("pygame_play_error: %s", exc)
            return False

    def stop(self) -> None:
        self._stopped = True
        if self._proc and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        # Also stop pygame mixer if active
        if not _USE_APLAY:
            try:
                import pygame
                if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                    pygame.mixer.music.stop()
            except Exception:
                pass

    def is_playing(self) -> bool:
        """Return True if audio is currently playing."""
        if self._stopped:
            return False
        if self._proc and self._proc.poll() is None:
            return True
        if not _USE_APLAY:
            try:
                import pygame
                if pygame.mixer.get_init() and pygame.mixer.music.get_busy():
                    return True
            except Exception:
                pass
        return False

    def release(self) -> None:
        self.stop()

    def ensure_stereo_16bit(self, audio_data: bytes, channels: int = 1) -> bytes:
        """Return int16 little-endian PCM audio bytes in stereo format."""
        import numpy as np
        if channels == 2:
            return audio_data
        mono = np.frombuffer(audio_data, dtype=np.int16)
        stereo = np.column_stack([mono, mono]).flatten()
        return stereo.tobytes()
