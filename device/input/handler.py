"""
BITOS Button Handler
Processes raw button press/release events into gesture types.
Desktop: Space bar = physical button.
"""

from __future__ import annotations

import os
import threading
import time
from enum import Enum, auto
from typing import Callable, Optional

import pygame


class ButtonEvent(Enum):
    SHORT_PRESS = auto()
    LONG_PRESS = auto()
    DOUBLE_PRESS = auto()
    TRIPLE_PRESS = auto()
    POWER_GESTURE = auto()
    HOLD_START = auto()
    HOLD_END = auto()


DEBOUNCE_MIN = 0.03
SHORT_THRESHOLD = 0.6
TRIPLE_WINDOW = 0.6
POWER_GESTURE_COUNT = 5
POWER_GESTURE_WINDOW_MS = 1200


class ButtonHandler:
    """Detect button gestures from raw press/release events."""

    def __init__(self):
        self._callbacks: dict[ButtonEvent, list[Callable]] = {e: [] for e in ButtonEvent}
        self._keyboard_mode = os.environ.get("BITOS_BUTTON", "").lower() == "keyboard"
        self._press_time: Optional[float] = None
        self._release_times: list[float] = []
        self._power_press_times: list[float] = []
        self._is_pressed = False
        self._pending_check_time: Optional[float] = None

    def on(self, event_type: ButtonEvent, callback: Callable):
        self._callbacks[event_type].append(callback)

    def _emit(self, event_type: ButtonEvent):
        for cb in self._callbacks[event_type]:
            try:
                cb()
            except Exception as exc:
                print(f"[ButtonHandler] Callback error for {event_type.name}: {exc}")

    def handle_pygame_event(self, event: pygame.event.Event) -> bool:
        if self._keyboard_mode and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self._emit(ButtonEvent.LONG_PRESS)
                return True
            if event.key == pygame.K_BACKSPACE:
                self._emit(ButtonEvent.DOUBLE_PRESS)
                return True
            if event.key == pygame.K_TAB:
                self._emit(ButtonEvent.TRIPLE_PRESS)
                return True

        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            self._on_press()
            return True
        if event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
            self._on_release()
            return True
        return False

    def _on_press(self):
        now = time.time()
        if self._is_pressed:
            return
        if self._press_time and (now - self._press_time) < DEBOUNCE_MIN:
            return

        self._is_pressed = True
        self._press_time = now

        cutoff = now - (POWER_GESTURE_WINDOW_MS / 1000.0)
        self._power_press_times = [t for t in self._power_press_times if t >= cutoff]
        self._power_press_times.append(now)
        if len(self._power_press_times) >= POWER_GESTURE_COUNT:
            self._power_press_times.clear()
            self._release_times.clear()
            self._pending_check_time = None
            self._emit(ButtonEvent.POWER_GESTURE)

        self._emit(ButtonEvent.HOLD_START)

    def _on_release(self):
        now = time.time()
        if not self._is_pressed:
            return

        self._is_pressed = False
        self._emit(ButtonEvent.HOLD_END)

        if self._press_time is None:
            return

        hold_duration = now - self._press_time
        if hold_duration >= SHORT_THRESHOLD:
            self._emit(ButtonEvent.LONG_PRESS)
            self._release_times.clear()
            self._pending_check_time = None
            return

        self._release_times.append(now)
        self._pending_check_time = now + TRIPLE_WINDOW

    def update(self):
        if self._pending_check_time is None:
            return

        now = time.time()
        if now < self._pending_check_time:
            return

        taps = len(self._release_times)
        self._release_times.clear()
        self._pending_check_time = None

        if taps >= 3:
            self._emit(ButtonEvent.TRIPLE_PRESS)
        elif taps == 2:
            self._emit(ButtonEvent.DOUBLE_PRESS)
        elif taps == 1:
            self._emit(ButtonEvent.SHORT_PRESS)


class GPIOButtonPoller:
    """Poll physical pin 11 via GPIO.input() every 20ms (no edge interrupts)."""

    GPIO_PIN_BOARD = 11
    POLL_INTERVAL = 0.02

    def __init__(self, on_press: Callable[[], None], on_release: Callable[[], None]):
        from hardware.whisplay_board import get_board

        self._board = get_board()
        self._on_press = on_press
        self._on_release = on_release
        self._running = self._board is not None
        self._last_state = False

        if not self._running:
            print("button_board_unavailable: falling back to keyboard-only input")
            return

        import RPi.GPIO as GPIO

        self._gpio = GPIO
        try:
            self._last_state = self._gpio.input(self.GPIO_PIN_BOARD) == self._gpio.HIGH
        except Exception:
            self._last_state = False

        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()

    def _poll(self):
        while self._running:
            try:
                state = self._gpio.input(self.GPIO_PIN_BOARD) == self._gpio.HIGH
                if state != self._last_state:
                    self._last_state = state
                    if state:
                        self._on_press()
                    else:
                        self._on_release()
            except Exception:
                pass
            time.sleep(self.POLL_INTERVAL)

    def stop(self):
        self._running = False


def create_button_handler():
    """WhisPlay mode uses GPIO polling; desktop mode uses keyboard events."""
    if os.environ.get("BITOS_BUTTON", "").lower() == "gpio":
        handler = ButtonHandler()
        handler._gpio_poller = GPIOButtonPoller(on_press=handler._on_press, on_release=handler._on_release)
        handler.handle_pygame_event = lambda event: False
        return handler
    return ButtonHandler()
