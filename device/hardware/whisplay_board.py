"""Singleton accessor for WhisPlayBoard — ensures only one instance is created."""

_instance = None


def get_board():
    global _instance
    if _instance is None:
        try:
            import sys, os, RPi.GPIO as GPIO
            sys.path.insert(0, os.environ.get(
                'WHISPLAY_DRIVER_PATH',
                '/home/pi/Whisplay/Driver'))
            GPIO.setwarnings(False)
            GPIO.cleanup()
            from WhisPlay import WhisPlayBoard
            _instance = WhisPlayBoard()
        except Exception as e:
            print(f"whisplay_board_init_failed: {e}")
    return _instance
