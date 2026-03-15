"""Pi Zero 2W built-in activity LED controller."""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_LED_TRIGGER = Path("/sys/class/leds/ACT/trigger")
_LED_BRIGHTNESS = Path("/sys/class/leds/ACT/brightness")


def _write(path: Path, value: str) -> bool:
    try:
        path.write_text(value)
        return True
    except Exception as exc:
        logger.debug("pi_led_write_failed path=%s error=%s", path, exc)
        return False


def set_pi_led(on: bool) -> None:
    """Turn the Pi activity LED on or off."""
    _write(_LED_TRIGGER, "none")
    _write(_LED_BRIGHTNESS, "1" if on else "0")


def restore_pi_led_activity() -> None:
    """Restore default disk activity behavior."""
    _write(_LED_TRIGGER, "mmc0")


def pulse_pi_led(count: int = 3) -> None:
    """Quick blink for visual feedback (blocking, use sparingly)."""
    import time

    _write(_LED_TRIGGER, "none")
    for _ in range(count):
        _write(_LED_BRIGHTNESS, "1")
        time.sleep(0.1)
        _write(_LED_BRIGHTNESS, "0")
        time.sleep(0.1)
