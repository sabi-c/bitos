import os
import sys

sys.path.insert(0, os.environ.get("WHISPLAY_DRIVER_PATH", "/home/pi/Whisplay/Driver"))


class LEDController:
    def __init__(self):
        self._board = None
        try:
            from WhisPlay import WhisPlayBoard

            self._board = WhisPlayBoard()
        except Exception as e:
            print(f"led_init_failed: {e}")

    def set_color(self, r, g, b):
        if self._board:
            try:
                self._board.set_led(r, g, b)
            except Exception:
                pass

    def off(self):
        self.set_color(0, 0, 0)

    def thinking(self):
        """Blue pulse — AI is processing"""
        self.set_color(0, 0, 255)

    def listening(self):
        """Green — recording voice"""
        self.set_color(0, 255, 0)

    def speaking(self):
        """White — playing response"""
        self.set_color(255, 255, 255)

    def error(self):
        """Red — something wrong"""
        self.set_color(255, 0, 0)
