"""
BITOS Button Handler
Processes raw button press/release events into gesture types.
Desktop: Space bar = physical button.
"""
import os
import threading
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
        self._keyboard_mode = os.environ.get("BITOS_BUTTON", "").lower() == "keyboard"
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

    def handle_pygame_event(self, event: pygame.event.Event) -> bool:
        """Process a Pygame keyboard event. Returns True when event is consumed as a button gesture."""
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


class GPIOButtonHandler:
    GPIO_PIN_BCM = 11
    POLL_INTERVAL = 0.02  # 20ms

    def __init__(self, on_event: Callable[[ButtonEvent], None]):
        self._on_event = on_event
        self._last_state = False
        self._press_time: Optional[float] = None
        self._running = True
        import RPi.GPIO as GPIO

        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        try:
            GPIO.setup(self.GPIO_PIN_BCM, GPIO.IN)
        except Exception as e:
            print(f"button_setup_failed: {e}")

        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()

    def _poll(self):
        import RPi.GPIO as GPIO

        while self._running:
            try:
                state = GPIO.input(self.GPIO_PIN_BCM)
                pressed = state == GPIO.HIGH
                if pressed != self._last_state:
                    self._last_state = pressed
                    if pressed:
                        self._press_time = time.time()
                    elif self._press_time:
                        duration = time.time() - self._press_time
                        self._press_time = None
                        if duration > 1.5:
                            self._on_event(ButtonEvent.LONG_PRESS)
                        elif duration > 0.05:
                            self._on_event(ButtonEvent.SHORT_PRESS)
            except Exception:
                pass
            time.sleep(self.POLL_INTERVAL)

    def stop(self):
        self._running = False


def create_button_handler():
    """Return a button handler for the current mode: WhisPlayBoard on Pi, keyboard/pygame on desktop."""
    if os.environ.get("BITOS_BUTTON", "").lower() == "gpio":
        handler = ButtonHandler()
        # Poll GPIO button — events feed into handler._emit
        handler._gpio = GPIOButtonHandler(on_event=handler._emit)
        # GPIO path: pygame events are ignored, update() is a no-op
        handler.handle_pygame_event = lambda event: False
        handler.update = lambda: None
        return handler
    return ButtonHandler()
