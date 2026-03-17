"""Audio routing manager with music ducking for BITOS.

Manages audio input/output routing based on connected devices.
Provides music ducking (volume fade) during agent TTS output.

Routes:
  - Output: AirPods (BT A2DP) when connected, else WM8960 speaker
  - Input: WM8960 mic (default), or AirPods HFP mic (if airpod_mic_mode=on)
"""
from __future__ import annotations

import asyncio
import logging
import subprocess
import threading
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bluetooth.audio_manager import BluetoothAudioManager

logger = logging.getLogger(__name__)

# Ducking parameters
_DUCK_VOLUME_PCT = 15       # Quiet background during TTS
_NORMAL_VOLUME_PCT = 100    # Full volume when not speaking
_FADE_STEPS = 5             # Number of volume steps for smooth fade
_FADE_INTERVAL_S = 0.05     # Seconds between fade steps


class AudioRouter:
    """Manages audio input/output routing based on connected devices.

    Routes:
      - Output: AirPods (BT A2DP) when connected, else WM8960 speaker
      - Input: WM8960 mic (default), or AirPods HFP mic (if airpod_mic_mode=on)
    """

    def __init__(self, bt_audio_manager: BluetoothAudioManager, repository=None):
        self._bt = bt_audio_manager
        self._repo = repository
        self._airpod_mode = False
        self._airpod_mic_enabled = False  # HFP mic toggle (off by default)
        self._music_ducked = False
        self._current_volume_pct = _NORMAL_VOLUME_PCT
        self._lock = threading.Lock()
        self._connected_device_type: str | None = None

        # Load settings from repository if available
        if self._repo:
            try:
                mic_setting = self._repo.get_setting("airpod_mic_mode")
                self._airpod_mic_enabled = str(mic_setting).lower() in ("on", "true", "1")
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def airpod_mode(self) -> bool:
        """Whether AirPods are the active audio output."""
        return self._airpod_mode

    @property
    def output_device(self) -> str:
        """Current audio output: 'airpods', 'headphones', or 'speaker'."""
        if self._airpod_mode:
            return "airpods"
        if self._bt.is_audio_routed_to_bt():
            return "headphones"
        return "speaker"

    @property
    def input_device(self) -> str:
        """Current audio input: 'wm8960' or 'airpods_hfp'."""
        if self._airpod_mode and self._airpod_mic_enabled:
            return "airpods_hfp"
        return "wm8960"

    @property
    def is_ducked(self) -> bool:
        """Whether music is currently ducked for agent speech."""
        return self._music_ducked

    @property
    def device_type(self) -> str | None:
        """Type of connected BT audio device ('airpods', 'headphones', or None)."""
        return self._connected_device_type

    # ------------------------------------------------------------------
    # Mode management
    # ------------------------------------------------------------------

    def enter_airpod_mode(self, device_type: str = "airpods") -> None:
        """Called when AirPods connect. Switches UI and audio routing."""
        with self._lock:
            self._airpod_mode = True
            self._connected_device_type = device_type
        logger.info("[AUDIO-ROUTER] entered airpod mode (type=%s)", device_type)

    def exit_airpod_mode(self) -> None:
        """Called when AirPods disconnect. Restores speaker routing."""
        with self._lock:
            was_ducked = self._music_ducked
            self._airpod_mode = False
            self._connected_device_type = None
            self._music_ducked = False

        if was_ducked:
            self._set_sink_volume(_NORMAL_VOLUME_PCT)

        logger.info("[AUDIO-ROUTER] exited airpod mode")

    def on_bt_connect(self, address: str, device_info: dict) -> None:
        """Handle BT audio device connection. Auto-detects AirPods."""
        name = device_info.get("name", "")
        device_type = detect_device_type(name)
        self._connected_device_type = device_type

        if device_type == "airpods":
            self.enter_airpod_mode(device_type)
        else:
            logger.info("[AUDIO-ROUTER] BT device connected: %s (type=%s)", name, device_type)

    def on_bt_disconnect(self, address: str) -> None:
        """Handle BT audio device disconnection."""
        if self._airpod_mode:
            self.exit_airpod_mode()
        self._connected_device_type = None
        logger.info("[AUDIO-ROUTER] BT device disconnected: %s", address)

    def set_airpod_mic(self, enabled: bool) -> None:
        """Toggle AirPod HFP mic input (vs WM8960 mic)."""
        self._airpod_mic_enabled = enabled
        if self._repo:
            self._repo.set_setting("airpod_mic_mode", "on" if enabled else "off")
        logger.info("[AUDIO-ROUTER] airpod mic: %s", "on" if enabled else "off")

    # ------------------------------------------------------------------
    # Music ducking
    # ------------------------------------------------------------------

    def duck_audio(self, target_volume_pct: int = _DUCK_VOLUME_PCT) -> None:
        """Lower music volume for agent speech (smooth fade down).

        Uses pactl to adjust the PulseAudio/PipeWire default sink volume.
        This is faster and more reliable than Spotify API volume control.
        """
        with self._lock:
            if self._music_ducked:
                return
            self._music_ducked = True

        current = self._current_volume_pct
        self._fade_volume(current, target_volume_pct)
        logger.debug("[AUDIO-ROUTER] ducked audio to %d%%", target_volume_pct)

    def restore_audio(self, target_volume_pct: int = _NORMAL_VOLUME_PCT) -> None:
        """Restore music volume after agent speech (smooth fade up)."""
        with self._lock:
            if not self._music_ducked:
                return
            self._music_ducked = False

        current = self._current_volume_pct
        self._fade_volume(current, target_volume_pct)
        logger.debug("[AUDIO-ROUTER] restored audio to %d%%", target_volume_pct)

    def _fade_volume(self, from_pct: int, to_pct: int) -> None:
        """Smoothly fade volume between two levels."""
        if from_pct == to_pct:
            return

        for step in range(_FADE_STEPS):
            progress = (step + 1) / _FADE_STEPS
            vol = int(from_pct + (to_pct - from_pct) * progress)
            self._set_sink_volume(vol)
            time.sleep(_FADE_INTERVAL_S)

        self._current_volume_pct = to_pct

    @staticmethod
    def _set_sink_volume(volume_pct: int) -> bool:
        """Set PulseAudio/PipeWire default sink volume."""
        try:
            subprocess.run(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{volume_pct}%"],
                capture_output=True,
                timeout=2,
            )
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception) as exc:
            logger.debug("[AUDIO-ROUTER] set-sink-volume failed: %s", exc)
            return False

    def is_music_playing(self) -> bool:
        """Check if music is currently playing via PulseAudio sink inputs.

        Returns True if there are active playback streams on a BT sink.
        """
        try:
            result = subprocess.run(
                ["pactl", "list", "short", "sink-inputs"],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0 and result.stdout.strip():
                return len(result.stdout.strip().splitlines()) > 0
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            pass
        return False

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Return current audio routing status."""
        return {
            "output": self.output_device,
            "input": self.input_device,
            "airpod_mode": self._airpod_mode,
            "airpod_mic": self._airpod_mic_enabled,
            "ducked": self._music_ducked,
            "device_type": self._connected_device_type,
            "volume_pct": self._current_volume_pct,
        }


def detect_device_type(name: str) -> str:
    """Detect device type from Bluetooth device name.

    Returns 'airpods', 'headphones', or 'speaker'.
    """
    lower = name.lower()
    if "airpods" in lower:
        return "airpods"
    # Common BT speaker patterns
    if any(kw in lower for kw in ("speaker", "soundbar", "boombox", "jbl", "sonos", "echo")):
        return "speaker"
    return "headphones"
