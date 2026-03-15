"""Singleton accessor for WhisPlayBoard — ensures only one instance is created.

WhisPlayBoard owns ALL GPIO on the Whisplay HAT: display (SPI + ST7789),
backlight, button, and LED.  It must be the first and only thing to
initialize GPIO.
"""

_instance = None


def get_board():
    global _instance
    if _instance is None:
        try:
            import os
            import sys
            import time

            sys.path.insert(0, os.environ.get(
                "WHISPLAY_DRIVER_PATH",
                "/home/pi/Whisplay/Driver",
            ))
            import RPi.GPIO as GPIO

            GPIO.setwarnings(False)
            GPIO.cleanup()
            time.sleep(0.5)

            from WhisPlay import WhisPlayBoard

            _instance = WhisPlayBoard()
            _instance.set_backlight(100)
        except Exception as e:
            print(f"whisplay_board_init_failed: {e}")
            return None
    return _instance
