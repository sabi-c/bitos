"""
BITOS Button Handler
Processes raw button press/release events into gesture types.
Desktop: Space bar = physical button.
"""
import time
from enum import Enum, auto
from typing import Callable, Optional

import pygame


class ButtonEvent(Enum):
    SHORT_PRESS = auto()   # < 600ms tap
    LONG_PRESS = auto()    # >= 600ms hold
    DOUBLE_PRESS = auto()  # 2 taps within 400ms
    TRIPLE_PRESS = auto()  # 3 taps within 600ms
    POWER_GESTURE = auto() # 5 presses within power gesture window
    HOLD_START = auto()    # Button down (for recording)
    HOLD_END = auto()      # Button up (stop recording)


# Timing constants (seconds)
DEBOUNCE_MIN = 0.03       # 30ms debounce
SHORT_THRESHOLD = 0.6     # <600ms = short press
DOUBLE_WINDOW = 0.4       # Window for double-press detection
TRIPLE_WINDOW = 0.6       # Window for triple-press detection
POWER_GESTURE_COUNT = 5
POWER_GESTURE_WINDOW_MS = 1200


class ButtonHandler:
    """Detects button gestures from raw press/release events."""

    def __init__(self):
        self._callbacks: dict[ButtonEvent, list[Callable]] = {e: [] for e in ButtonEvent}
        self._press_time: Optional[float] = None
        self._release_times: list[float] = []
        self._power_press_times: list[float] = []
        self._is_pressed = False
        self._long_press_fired = False
        self._pending_check_time: Optional[float] = None

    def on(self, event_type: ButtonEvent, callback: Callable):
        """Register a callback for a button event."""
        self._callbacks[event_type].append(callback)

    def _emit(self, event_type: ButtonEvent):
        """Fire all callbacks for an event type."""
        for cb in self._callbacks[event_type]:
            try:
                cb()
            except Exception as e:
                print(f"[ButtonHandler] Callback error for {event_type.name}: {e}")

    def handle_pygame_event(self, event: pygame.event.Event):
        """Process a Pygame keyboard event (Space = button)."""
        if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
            self._on_press()
        elif event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
            self._on_release()

    def _on_press(self):
        now = time.time()
        if self._is_pressed:
            return
        if self._press_time and (now - self._press_time) < DEBOUNCE_MIN:
            return

        self._is_pressed = True
        self._press_time = now
        self._long_press_fired = False

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

        # Long press
        if hold_duration >= SHORT_THRESHOLD:
            self._emit(ButtonEvent.LONG_PRESS)
            self._release_times.clear()
            self._pending_check_time = None
            return

        # Short press — accumulate for multi-tap detection
        self._release_times.append(now)
        self._pending_check_time = now + TRIPLE_WINDOW

    def update(self):
        """Call every frame to finalize multi-tap detection."""
        if self._pending_check_time is None:
            return

        now = time.time()
        if now < self._pending_check_time:
            return

        # Check accumulated taps
        tap_count = len(self._release_times)
        self._release_times.clear()
        self._pending_check_time = None

        if tap_count >= 3:
            self._emit(ButtonEvent.TRIPLE_PRESS)
        elif tap_count == 2:
            self._emit(ButtonEvent.DOUBLE_PRESS)
        elif tap_count == 1:
            self._emit(ButtonEvent.SHORT_PRESS)
