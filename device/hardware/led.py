"""WhisPlay RGB LED controller."""

from __future__ import annotations


class LEDController:
    def __init__(self):
        self._board = None
        try:
            from hardware.whisplay_board import get_board

            self._board = get_board()
        except Exception as exc:
            print(f"led_init_failed: {exc}")

    def set_color(self, r: int, g: int, b: int):
        if self._board is not None:
            try:
                self._board.set_rgb(r, g, b)
            except Exception:
                pass

    def off(self):
        self.set_color(0, 0, 0)

    def thinking(self):
        self.set_color(0, 0, 255)

    def listening(self):
        self.set_color(0, 255, 0)

    def speaking(self):
        self.set_color(255, 255, 255)

    def error(self):
        self.set_color(255, 0, 0)
