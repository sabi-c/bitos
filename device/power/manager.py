"""BITOS Power Manager — adaptive FPS, display dim/sleep, system power saving.

Centralizes power-related decisions:
- Tracks user activity and drives adaptive frame rate
- Exposes should_dim() / should_sleep() for display control
- Runs one-shot system power commands (HDMI off, BT off, WiFi power_save)

Works alongside IdleManager (which owns brightness) — this module owns
FPS adaptation and system-level power toggles.

Usage in main loop:
    power = PowerManager()
    power.system_power_save()          # once at boot
    # On any user input:
    power.poke()
    # Each frame:
    fps = power.get_target_fps()
    clock.tick(fps)
"""

import logging
import platform
import subprocess
import time

logger = logging.getLogger(__name__)

# Defaults
DIM_AFTER_S = 30
SLEEP_AFTER_S = 120
FPS_ACTIVE = 15
FPS_IDLE = 5


class PowerManager:
    """Adaptive power management for Pi Zero 2W."""

    def __init__(
        self,
        dim_after: float = DIM_AFTER_S,
        sleep_after: float = SLEEP_AFTER_S,
        fps_active: int = FPS_ACTIVE,
        fps_idle: int = FPS_IDLE,
    ):
        self.dim_after = max(0, float(dim_after))
        self.sleep_after = max(0, float(sleep_after))
        self.fps_active = max(1, int(fps_active))
        self.fps_idle = max(1, int(fps_idle))
        self._last_activity = time.monotonic()
        self._is_linux = platform.system() == "Linux"

    @property
    def idle_seconds(self) -> float:
        """Seconds since last user interaction."""
        return time.monotonic() - self._last_activity

    def poke(self) -> None:
        """Call on any user interaction to reset the activity timer."""
        self._last_activity = time.monotonic()

    def should_dim(self) -> bool:
        """True when idle long enough to dim the display."""
        if self.dim_after == 0:
            return False
        return self.idle_seconds >= self.dim_after

    def should_sleep(self) -> bool:
        """True when idle long enough to sleep the display."""
        if self.sleep_after == 0:
            return False
        return self.idle_seconds >= self.sleep_after

    def get_target_fps(self) -> int:
        """Return adaptive FPS: lower when idle, full when active."""
        if self.should_dim():
            return self.fps_idle
        return self.fps_active

    # ── System-level power saving ────────────────────────────────

    def system_power_save(self) -> None:
        """Disable HDMI/BT and enable WiFi power_save. No-op on non-Linux."""
        if not self._is_linux:
            logger.debug("power_save skipped (not Linux)")
            return

        commands = [
            # Disable HDMI output (Pi Zero has no display connected)
            ["tvservice", "-o"],
            # Disable Bluetooth (not used — we use WiFi only)
            ["rfkill", "block", "bluetooth"],
            # Enable WiFi power management (idle power saving)
            ["iwconfig", "wlan0", "power", "on"],
        ]

        for cmd in commands:
            try:
                subprocess.run(
                    cmd,
                    capture_output=True,
                    timeout=5,
                    check=False,
                )
                logger.info("power_save cmd=%s ok", " ".join(cmd))
            except FileNotFoundError:
                logger.debug("power_save cmd=%s not_found", cmd[0])
            except subprocess.TimeoutExpired:
                logger.warning("power_save cmd=%s timeout", " ".join(cmd))
            except Exception as exc:
                logger.warning("power_save cmd=%s error=%s", " ".join(cmd), exc)

    def wifi_power_save(self, enable: bool = True) -> None:
        """Toggle WiFi power management. Call with False during active voice."""
        if not self._is_linux:
            return
        mode = "on" if enable else "off"
        try:
            subprocess.run(
                ["iwconfig", "wlan0", "power", mode],
                capture_output=True,
                timeout=5,
                check=False,
            )
            logger.info("wifi_power_save=%s", mode)
        except Exception as exc:
            logger.debug("wifi_power_save error=%s", exc)
