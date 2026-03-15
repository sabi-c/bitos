"""
BITOS Button Handler
Processes raw button press/release events into gesture types.
Desktop: Space bar = physical button.
"""

from __future__ import annotations

import os
import sys
import time
import logging
from enum import Enum, auto
from typing import Callable, Optional

import pygame


logger = logging.getLogger(__name__)


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

    def __init__(self, active_screen_name_getter: Callable[[], str] | None = None):
        self._callbacks: dict[ButtonEvent, list[Callable]] = {e: [] for e in ButtonEvent}
        self._keyboard_mode = os.environ.get("BITOS_BUTTON", "").lower() == "keyboard"
        self._active_screen_name_getter = active_screen_name_getter
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
        self._log_button_state(pressed=True)

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
        self._log_button_state(pressed=False)
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

    def _log_button_state(self, pressed: bool):
        screen_name = "unknown"
        if self._active_screen_name_getter is not None:
            try:
                screen_name = self._active_screen_name_getter()
            except Exception:
                screen_name = "unknown"
        state = "pressed" if pressed else "released"
        logger.info("Button %s — active screen: %s", state, screen_name)


def create_button_handler(board=None, active_screen_name_getter: Callable[[], str] | None = None):
    """Create a button handler, preferring WhisPlay board callbacks when available."""
    import sys

    _on_pi = sys.platform == "linux" and os.path.exists("/proc/device-tree/model")
    mode_raw = os.environ.get("BITOS_BUTTON", "")
    mode_default = "gpio" if _on_pi else "keyboard"
    mode = mode_raw if mode_raw else mode_default
    logger.info(
        "button_init platform=%s on_pi=%s BITOS_BUTTON=%r effective_mode=%s board=%s",
        sys.platform,
        _on_pi,
        mode_raw,
        mode,
        board,
    )

    handler = ButtonHandler(active_screen_name_getter=active_screen_name_getter)
    button_mode = mode.lower()

    if board is None and button_mode == "gpio":
        from hardware.whisplay_board import get_board

        board = get_board()

    if board is not None:
        board.on_button_press(handler._on_press)
        board.on_button_release(handler._on_release)
        handler.handle_pygame_event = lambda event: False
        return handler

    if button_mode == "gpio":
        print("button_board_unavailable: falling back to keyboard-only input")
    return handler
