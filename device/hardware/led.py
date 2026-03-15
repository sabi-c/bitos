"""WhisPlay RGB LED controller."""

from __future__ import annotations

import logging


logger = logging.getLogger(__name__)


class LEDController:
    def __init__(self, board=None):
        self._board = board
        if self._board is None:
            try:
                from hardware.whisplay_board import get_board

                self._board = get_board()
            except Exception as exc:
                logger.warning("led_init_failed error=%s", exc)

    def set_color(self, r: int, g: int, b: int):
        if self._board is not None:
            try:
                self._board.set_rgb(r, g, b)
            except Exception:
                logger.debug("led_set_color_failed r=%s g=%s b=%s", r, g, b)

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
