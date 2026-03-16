"""
BITOS Button Handler
Processes raw button press/release events into gesture types.
Desktop: Space bar = physical button.
"""

from __future__ import annotations

import os
import time
import logging
from enum import Enum, auto
from typing import Callable

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


DEBOUNCE_S = 0.020
LONG_PRESS_S = 0.400
CLICK_TIMEOUT_S = 0.200          # was 0.300 — tighter window for snappier single-press
POWER_PRESS_COUNT = 5
POWER_WINDOW_S = 1.200

# Back-compat aliases used internally
DEBOUNCE_MIN = DEBOUNCE_S
SHORT_THRESHOLD = LONG_PRESS_S
DOUBLE_WINDOW = CLICK_TIMEOUT_S
TRIPLE_WINDOW = CLICK_TIMEOUT_S


class ButtonHandler:
    """Detect button gestures from raw press/release events."""

    def __init__(self, active_screen_name_getter: Callable[[], str] | None = None):
        self._callbacks: dict[ButtonEvent, list[Callable]] = {e: [] for e in ButtonEvent}
        self._keyboard_mode = os.environ.get("BITOS_BUTTON", "").lower() == "keyboard"
        self._active_screen_name_getter = active_screen_name_getter

        # Physical state / edge timing.
        self._pressed = False
        self._press_time: float = 0.0
        self._last_edge_time: float = 0.0
        self._raw_pressed = False
        self._long_emitted_for_press = False

        # Multi-click classification window.
        self._click_count = 0
        self._click_deadline: float | None = None

        # Immediate-short mode: when True, SHORT_PRESS fires on release
        # with zero delay (no multi-click window).  Screens that only need
        # single-tap navigation can set this for instant response.
        self._immediate_short = False

        # Power gesture tracking.
        self._power_press_times: list[float] = []

        self._board = None
        self._poll_board_state = True

    def on(self, event_type: ButtonEvent, callback: Callable):
        self._callbacks[event_type].append(callback)

    def set_immediate_short(self, enabled: bool) -> None:
        """Toggle immediate-short mode.

        When *enabled*, SHORT_PRESS fires the instant the button is
        released (zero latency).  Multi-click detection (DOUBLE / TRIPLE)
        is bypassed — only SHORT_PRESS and LONG_PRESS are emitted.

        Screens that rely only on tap-to-scroll should enable this for
        snappier navigation.  Screens that need double/triple should
        disable it (the default).
        """
        self._immediate_short = enabled
        if enabled:
            # Flush any pending multi-click state so a stale deadline
            # doesn't fire after mode switch.
            self._click_count = 0
            self._click_deadline = None

    def _emit(self, event_type: ButtonEvent):
        for cb in self._callbacks[event_type]:
            try:
                cb()
            except Exception as exc:
                logger.error("button_callback_error event=%s error=%s", event_type.name, exc)

    def handle_pygame_event(self, event: pygame.event.Event) -> bool:
        if self._keyboard_mode and event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                self._emit(ButtonEvent.DOUBLE_PRESS)
                return True
            if event.key == pygame.K_BACKSPACE:
                self._emit(ButtonEvent.LONG_PRESS)
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
        if now - self._last_edge_time < DEBOUNCE_S:
            return
        self._last_edge_time = now

        if self._pressed:
            return

        self._pressed = True
        self._press_time = now
        self._long_emitted_for_press = False
        self._log_button_state(pressed=True)

        cutoff = now - POWER_WINDOW_S
        self._power_press_times = [t for t in self._power_press_times if t >= cutoff]
        self._power_press_times.append(now)
        if len(self._power_press_times) >= POWER_PRESS_COUNT:
            self._power_press_times.clear()
            self._pressed = False
            self._long_emitted_for_press = False
            self._click_count = 0
            self._click_deadline = None
            self._emit(ButtonEvent.POWER_GESTURE)
            return

        self._emit(ButtonEvent.HOLD_START)

    def _on_release(self):
        now = time.time()
        if now - self._last_edge_time < DEBOUNCE_S:
            return
        if not self._pressed:
            return

        self._last_edge_time = now
        self._pressed = False
        self._log_button_state(pressed=False)
        self._emit(ButtonEvent.HOLD_END)

        if self._long_emitted_for_press:
            self._long_emitted_for_press = False
            self._click_count = 0
            self._click_deadline = None
            return

        duration = now - self._press_time
        if duration >= LONG_PRESS_S:
            self._long_emitted_for_press = True
            self._emit(ButtonEvent.LONG_PRESS)
            self._click_count = 0
            self._click_deadline = None
            return

        # Immediate-short mode: fire SHORT_PRESS on release with zero latency.
        # Skips the multi-click classification window entirely.
        if self._immediate_short:
            self._click_count = 0
            self._click_deadline = None
            self._emit(ButtonEvent.SHORT_PRESS)
            return

        if self._click_deadline is None or now > self._click_deadline:
            self._click_count = 1
        else:
            self._click_count = min(3, self._click_count + 1)
        self._click_deadline = now + CLICK_TIMEOUT_S

    def update(self) -> None:
        now = time.time()

        if self._poll_board_state and self._board is None and not self._keyboard_mode:
            try:
                from hardware.whisplay_board import get_board

                self._board = get_board()
            except Exception:
                self._board = None

        if self._poll_board_state and self._board is not None:
            pressed = self._board.button_pressed()
            if pressed and not self._raw_pressed:
                self._raw_pressed = True
                self._on_press()
            elif not pressed and self._raw_pressed:
                self._raw_pressed = False
                self._on_release()

        if self._pressed and not self._long_emitted_for_press and now - self._press_time >= LONG_PRESS_S:
            self._long_emitted_for_press = True
            self._click_count = 0
            self._click_deadline = None
            self._emit(ButtonEvent.LONG_PRESS)

        if not self._pressed and self._click_deadline is not None and now >= self._click_deadline:
            if self._click_count == 1:
                self._emit(ButtonEvent.SHORT_PRESS)
            elif self._click_count == 2:
                self._emit(ButtonEvent.DOUBLE_PRESS)
            elif self._click_count >= 3:
                self._emit(ButtonEvent.TRIPLE_PRESS)
            self._click_count = 0
            self._click_deadline = None

    def _log_button_state(self, pressed: bool):
        if not logger.isEnabledFor(logging.DEBUG):
            return

        screen_name = "unknown"
        if self._active_screen_name_getter is not None:
            try:
                screen_name = self._active_screen_name_getter()
            except Exception:
                screen_name = "unknown"
        state = "pressed" if pressed else "released"
        logger.debug("Button %s — active screen: %s", state, screen_name)


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
        handler._board = board
        handler._poll_board_state = True  # polling fallback if edge detection fails
        board.on_button_press(handler._on_press)
        board.on_button_release(handler._on_release)
        handler.handle_pygame_event = lambda event: False
        logger.info("board_button_init: callbacks registered + polling fallback enabled")
        return handler

    if button_mode == "gpio":
        logger.warning("button_board_unavailable: falling back to keyboard-only input")
    return handler
