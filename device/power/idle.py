"""Idle sleep manager — dims and sleeps the display after inactivity.

Tracks last user activity timestamp. After sleep_timeout_seconds of
inactivity, shows an ambient clock at 30% brightness. After 2x timeout,
turns display off (0%). Any button press wakes the display instantly.

Usage in main loop:
    idle_mgr = IdleManager(driver, repository, screen_manager=screen_mgr)
    # On any button event:
    idle_mgr.wake()
    # Each frame:
    idle_mgr.tick()
"""

import logging
import time

logger = logging.getLogger(__name__)

# Brightness levels
BRIGHTNESS_FULL = 100
BRIGHTNESS_DIM = 30
BRIGHTNESS_OFF = 0


class IdleManager:
    """Track idle time and control display brightness accordingly."""

    def __init__(self, driver, repository, default_timeout: int = 60,
                 screen_manager=None):
        self._driver = driver
        self._repo = repository
        self._default_timeout = default_timeout
        self._screen_manager = screen_manager
        self._last_activity = time.time()
        self._current_brightness = BRIGHTNESS_FULL
        self._state = "awake"  # awake | dim | sleep
        self._ambient_clock_pushed = False

    @property
    def timeout(self) -> int:
        """Read sleep timeout from repository. 0 means never sleep."""
        try:
            val = int(self._repo.get_setting("sleep_timeout_seconds", self._default_timeout) or self._default_timeout)
            return max(0, val)
        except (ValueError, TypeError):
            return self._default_timeout

    @property
    def state(self) -> str:
        return self._state

    def wake(self) -> None:
        """Call on any user input to reset idle timer and restore brightness."""
        self._last_activity = time.time()
        if self._state != "awake":
            self._pop_ambient_clock()
            self._set_brightness(BRIGHTNESS_FULL)
            self._state = "awake"
            logger.debug("idle_wake")

    def tick(self) -> None:
        """Call each frame to check idle state transitions."""
        timeout = self.timeout
        if timeout == 0:
            # Never sleep
            if self._state != "awake":
                self._pop_ambient_clock()
                self._set_brightness(BRIGHTNESS_FULL)
                self._state = "awake"
            return

        idle_seconds = time.time() - self._last_activity

        if self._state == "awake" and idle_seconds >= timeout:
            self._set_brightness(BRIGHTNESS_DIM)
            self._push_ambient_clock()
            self._state = "dim"
            logger.debug("idle_dim after=%ds", int(idle_seconds))

        elif self._state == "dim" and idle_seconds >= timeout * 2:
            self._set_brightness(BRIGHTNESS_OFF)
            self._state = "sleep"
            logger.debug("idle_sleep after=%ds", int(idle_seconds))

    def _push_ambient_clock(self) -> None:
        """Push ambient clock screen onto the screen manager stack."""
        if self._ambient_clock_pushed or self._screen_manager is None:
            return
        try:
            from screens.ambient_clock import AmbientClockScreen
            self._screen_manager.push(AmbientClockScreen())
            self._ambient_clock_pushed = True
            logger.debug("ambient_clock_pushed")
        except Exception as exc:
            logger.debug("ambient_clock_push_failed: %s", exc)

    def _pop_ambient_clock(self) -> None:
        """Pop ambient clock screen if we pushed one."""
        if not self._ambient_clock_pushed or self._screen_manager is None:
            return
        try:
            current = self._screen_manager.current
            if current is not None and type(current).__name__ == "AmbientClockScreen":
                self._screen_manager.pop()
                logger.debug("ambient_clock_popped")
        except Exception as exc:
            logger.debug("ambient_clock_pop_failed: %s", exc)
        self._ambient_clock_pushed = False

    def _set_brightness(self, level: int) -> None:
        if level == self._current_brightness:
            return
        self._current_brightness = level
        if hasattr(self._driver, "set_brightness"):
            try:
                self._driver.set_brightness(level)
            except Exception as exc:
                logger.debug("set_brightness_failed level=%s error=%s", level, exc)
