import logging
import sys
import os

logger = logging.getLogger(__name__)

_instance = None


def get_board():
    global _instance
    if _instance is not None:
        return _instance
    try:
        sys.path.insert(0, os.environ.get(
            'WHISPLAY_DRIVER_PATH',
            '/home/pi/Whisplay/Driver'))
        from WhisPlay import WhisPlayBoard
        try:
            import RPi.GPIO as _GPIO
            _GPIO.remove_event_detect(11)
        except Exception:
            pass
        _instance = WhisPlayBoard()
        _instance.set_backlight(100)
        logger.info("whisplay_board_init_ok")
    except Exception as e:
        logger.warning("whisplay_board_init_failed: %s", e)
        _instance = None
    return _instance
