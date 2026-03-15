"""
BITOS Button Handler
Processes raw button press/release events into gesture types.
Desktop: Space bar = physical button.
"""
import os
import sys
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
    """GPIO-backed button handler for Pi hardware mode.

    Prefers WhisPlayBoard.set_key_callback() to avoid conflicting GPIO listeners.
    Falls back to direct RPi.GPIO on BCM 17 if the Whisplay driver is unavailable.
    """

    GPIO_PIN_BCM = 17  # BCM 17 = Board P11 (Whisplay HAT button)

    def __init__(self, on_event: Callable[[ButtonEvent], None]):
        self._on_event = on_event
        self._press_times: list[float] = []
        self._press_start: float | None = None
        self._lock = threading.Lock()
        self._whisplay_board = None

        # Strategy 1: Use WhisPlayBoard's own button callback (avoids GPIO conflict)
        try:
            sys.path.insert(0, os.environ.get("WHISPLAY_DRIVER_PATH", "/home/pi/Whisplay/Driver"))
            from WhisPlay import WhisPlayBoard
            board = WhisPlayBoard()
            board.set_key_callback(self._raw_callback_whisplay)
            self._whisplay_board = board
            return  # Success — no direct GPIO needed
        except (ImportError, AttributeError, Exception):
            pass  # WhisPlay unavailable or no set_key_callback — fall through

        # Strategy 2: Direct GPIO (BCM numbering, consistent with display driver)
        import RPi.GPIO as GPIO  # type: ignore
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self.GPIO_PIN_BCM, GPIO.IN, pull_up_down=GPIO.PUD_UP)
        GPIO.add_event_detect(
            self.GPIO_PIN_BCM,
            GPIO.BOTH,
            callback=self._raw_callback,
            bouncetime=30,
        )

    def _raw_callback_whisplay(self, pin_state: int):
        """Callback from WhisPlayBoard: pin_state 0=pressed, 1=released."""
        now_ms = time.time() * 1000.0
        if pin_state == 0:
            with self._lock:
                self._press_start = now_ms
            return
        with self._lock:
            start_ms = self._press_start if self._press_start is not None else now_ms
        duration_ms = now_ms - start_ms
        self._handle_release(duration_ms=duration_ms, now_ms=now_ms)

    def _raw_callback(self, channel):
        import RPi.GPIO as GPIO  # type: ignore

        now_ms = time.time() * 1000.0
        if GPIO.input(channel) == GPIO.LOW:
            with self._lock:
                self._press_start = now_ms
            return

        with self._lock:
            start_ms = self._press_start if self._press_start is not None else now_ms
        duration_ms = now_ms - start_ms
        self._handle_release(duration_ms=duration_ms, now_ms=now_ms)

    def _handle_release(self, duration_ms: float, now_ms: float) -> None:
        short_threshold_ms = SHORT_THRESHOLD * 1000.0
        double_window_ms = DOUBLE_WINDOW * 1000.0
        triple_window_ms = TRIPLE_WINDOW * 1000.0

        with self._lock:
            if duration_ms >= short_threshold_ms:
                self._press_times.clear()
                self._on_event(ButtonEvent.LONG_PRESS)
                return

            self._press_times.append(now_ms)
            self._press_times = [t for t in self._press_times if (now_ms - t) < triple_window_ms]
            count = len(self._press_times)

        if count >= 3:
            with self._lock:
                self._press_times.clear()
            self._on_event(ButtonEvent.TRIPLE_PRESS)
            return

        if count == 2:
            def check_double():
                time.sleep(double_window_ms / 1000.0)
                with self._lock:
                    if len(self._press_times) < 3:
                        self._press_times.clear()
                        self._on_event(ButtonEvent.DOUBLE_PRESS)

            threading.Thread(target=check_double, daemon=True).start()
            return

        def check_single():
            time.sleep(double_window_ms / 1000.0)
            with self._lock:
                if len(self._press_times) == 1:
                    self._press_times.clear()
                    self._on_event(ButtonEvent.SHORT_PRESS)

        threading.Thread(target=check_single, daemon=True).start()


def create_button_handler():
    """Return a button handler for the current mode: GPIO on Pi, keyboard/pygame on desktop."""
    if os.environ.get("BITOS_BUTTON", "").lower() == "gpio":
        return GPIOButtonHandlerAdapter()
    return ButtonHandler()


class GPIOButtonHandlerAdapter(ButtonHandler):
    """Wraps GPIOButtonHandler so the main loop can use the same .on() / handle_pygame_event / update API."""

    def __init__(self):
        super().__init__()
        self._gpio = GPIOButtonHandler(on_event=self._emit)

    def handle_pygame_event(self, event: pygame.event.Event) -> bool:
        return False  # GPIO path: events come from callback, not pygame

    def update(self) -> None:
        pass  # GPIO path: no per-frame tap resolution needed (handled in GPIOButtonHandler)
