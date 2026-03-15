"""BITOS LED Controller for WhisPlay RGB LED states."""

from __future__ import annotations

import logging
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
        step = 0
        while True:
            with self._lock:
                if not self._running:
                    break

            if name == "pulse_white":
                brightness = int(abs(30 * ((step % 40) / 20.0 - 1)))
                self._set_rgb(brightness, brightness, brightness)
                time.sleep(0.05)
            elif name == "blink_red":
                on = (step % 10) < 5
                self._set_rgb(120 if on else 0, 0, 0)
                time.sleep(0.1)
            elif name == "pulse_blue":
                brightness = int(abs(60 * ((step % 40) / 20.0 - 1)))
                self._set_rgb(0, 0, brightness)
                time.sleep(0.05)
            else:
                self._set_rgb(0, 0, 0)
                time.sleep(0.2)

            step += 1
