"""BITOS LED Controller for WhisPlay RGB LED states."""

from __future__ import annotations

import logging
import math
import threading
import time
from typing import Optional


logger = logging.getLogger(__name__)


class LEDController:
    def __init__(self, board=None):
        self._board = board
        self._state = "off"
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()

    def _set_rgb(self, r: int, g: int, b: int) -> None:
        if self._board is None:
            return
        try:
            self._board.set_rgb(r, g, b)
        except Exception as exc:
            logger.debug("led_set_error=%s", exc)

    def set_color(self, r: int, g: int, b: int) -> None:
        self._stop_animation()
        self._set_rgb(r, g, b)

    def off(self) -> None:
        self.set_color(0, 0, 0)
        self._state = "off"

    def idle(self) -> None:
        self.set_color(30, 30, 30)
        self._state = "idle"

    def thinking(self) -> None:
        self._start_animation("pulse_white")

    def listening(self) -> None:
        self._start_animation("pulse_blue")

    def speaking(self) -> None:
        self.set_color(50, 50, 50)
        self._state = "speaking"

    def connected(self) -> None:
        self.set_color(0, 60, 0)
        self._state = "connected"

    def low_battery(self) -> None:
        self.set_color(80, 40, 0)
        self._state = "low_battery"

    def critical_battery(self) -> None:
        self._start_animation("blink_red")

    def error(self) -> None:
        self._start_animation("blink_red")

    def ble_active(self) -> None:
        self._start_animation("pulse_blue")

    def recording(self) -> None:
        """Slow breathing red pulse (3s cycle). Indicates mic is active."""
        self._start_animation("breathing_red")

    def sending(self) -> None:
        """Fast cyan pulse (0.5s cycle). Indicates data being sent to server."""
        self._start_animation("pulse_cyan")

    def responding(self) -> None:
        """Gentle warm white wave (1s cycle, sinusoidal). Agent generating response."""
        self._start_animation("wave_warm_white")

    def success(self) -> None:
        """Brief green flash (0.3s on, fade out). One-shot, then returns to idle."""
        self._start_animation("flash_green")

    def battery_warning(self, pct: int) -> None:
        if pct <= 5:
            self.critical_battery()
        elif pct <= 15:
            self.low_battery()
        else:
            self.off()

    def _stop_animation(self) -> None:
        with self._lock:
            self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.5)

    def _start_animation(self, name: str) -> None:
        self._stop_animation()
        with self._lock:
            self._running = True
            self._state = name
        self._thread = threading.Thread(target=self._animate, args=(name,), daemon=True)
        self._thread.start()

    def _animate(self, name: str) -> None:
        TICK = 0.02  # 50 Hz update rate for smooth sinusoidal curves
        t0 = time.monotonic()

        while True:
            with self._lock:
                if not self._running:
                    break

            elapsed = time.monotonic() - t0

            if name == "pulse_white":
                # Original triangle wave, ~2s cycle
                phase = (elapsed % 2.0) / 2.0
                brightness = int(30 * abs(phase * 2.0 - 1.0))
                self._set_rgb(brightness, brightness, brightness)

            elif name == "blink_red":
                on = (elapsed % 1.0) < 0.5
                self._set_rgb(120 if on else 0, 0, 0)

            elif name == "pulse_blue":
                phase = (elapsed % 2.0) / 2.0
                brightness = int(60 * abs(phase * 2.0 - 1.0))
                self._set_rgb(0, 0, brightness)

            elif name == "breathing_red":
                # Slow breathing red: 3s cycle (1.5s inhale, 1.5s exhale)
                # sin gives smooth 0→1→0 over one full cycle
                phase = (elapsed % 3.0) / 3.0
                intensity = (math.sin(phase * 2.0 * math.pi - math.pi / 2.0) + 1.0) / 2.0
                r = int(10 + 90 * intensity)  # range 10..100
                self._set_rgb(r, 0, 0)

            elif name == "pulse_cyan":
                # Fast cyan pulse: 0.5s cycle
                phase = (elapsed % 0.5) / 0.5
                intensity = (math.sin(phase * 2.0 * math.pi - math.pi / 2.0) + 1.0) / 2.0
                val = int(15 + 80 * intensity)  # range 15..95
                self._set_rgb(0, val, val)

            elif name == "wave_warm_white":
                # Gentle warm white wave: 1s sinusoidal cycle
                phase = (elapsed % 1.0) / 1.0
                intensity = (math.sin(phase * 2.0 * math.pi - math.pi / 2.0) + 1.0) / 2.0
                # Warm white = slightly yellow-tinted
                r = int(20 + 50 * intensity)
                g = int(18 + 45 * intensity)
                b = int(12 + 30 * intensity)
                self._set_rgb(r, g, b)

            elif name == "flash_green":
                # One-shot: 0.3s bright green, then 0.5s fade, then idle
                if elapsed < 0.3:
                    self._set_rgb(0, 120, 0)
                elif elapsed < 0.8:
                    fade = 1.0 - (elapsed - 0.3) / 0.5
                    self._set_rgb(0, int(120 * fade), 0)
                else:
                    # Transition to idle and stop
                    self._set_rgb(30, 30, 30)
                    with self._lock:
                        self._running = False
                        self._state = "idle"
                    break

            else:
                self._set_rgb(0, 0, 0)

            time.sleep(TICK)
