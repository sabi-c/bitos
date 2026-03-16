"""
BITOS Display Driver
Abstract display interface + Pygame implementation for desktop development.
ST7789 hardware driver delegates to WhisPlayBoard, which owns all HAT GPIO.
"""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod

import pygame

try:
    import numpy as np

    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

from display.tokens import PHYSICAL_H, PHYSICAL_W, WINDOW_H, WINDOW_W, BLACK, FPS

logger = logging.getLogger(__name__)


class DisplayDriver(ABC):
    @abstractmethod
    def init(self):
        pass

    @abstractmethod
    def get_surface(self) -> pygame.Surface:
        pass

    @abstractmethod
    def update(self):
        pass

    @abstractmethod
    def quit(self):
        pass


class PygameDriver(DisplayDriver):
    def __init__(self):
        self._surface = None
        self._window = None
        self._clock = None

    def init(self):
        pygame.init()
        pygame.display.set_caption("BITOS")
        self._window = pygame.display.set_mode((WINDOW_W, WINDOW_H))
        self._surface = pygame.Surface((PHYSICAL_W, PHYSICAL_H))
        self._surface.fill(BLACK)
        self._clock = pygame.time.Clock()

    def get_surface(self) -> pygame.Surface:
        return self._surface

    def update(self):
        scaled = pygame.transform.scale(self._surface, (WINDOW_W, WINDOW_H))
        self._window.blit(scaled, (0, 0))
        pygame.display.flip()
        self._clock.tick(FPS)

    def quit(self):
        pygame.quit()

    def get_clock(self):
        return self._clock


class ST7789Driver(DisplayDriver):
    """Pushes frames using WhisPlayBoard.draw_image(...)."""

    WIDTH = 240
    HEIGHT = 280

    def __init__(self, board=None):
        self._surface: pygame.Surface | None = None
        self._board = board

    def init(self):
        if self._board is None:
            from hardware.whisplay_board import get_board

            self._board = get_board()
        if self._board is None:
            raise RuntimeError("WhisPlayBoard unavailable: get_board() returned None")

        pygame.init()
        self._surface = pygame.Surface((self.WIDTH, self.HEIGHT))
        self._surface.fill(BLACK)

        self._board.fill_screen(0)
        self._board.set_backlight(100)
        self._board.previous_frame = None

    def get_surface(self) -> pygame.Surface:
        if self._surface is None:
            raise RuntimeError("ST7789 surface unavailable: call init() first")
        return self._surface

    @staticmethod
    def _rgb888_to_rgb565(raw_rgb: bytes) -> list[int]:
        if _HAS_NUMPY:
            return ST7789Driver._rgb888_to_rgb565_numpy(raw_rgb)
        return ST7789Driver._rgb888_to_rgb565_python(raw_rgb)

    @staticmethod
    def _rgb888_to_rgb565_numpy(raw_rgb: bytes) -> list[int]:
        """Vectorized RGB888→RGB565 conversion using numpy (~10x faster)."""
        arr = np.frombuffer(raw_rgb, dtype=np.uint8).reshape(-1, 3)
        r = arr[:, 0].astype(np.uint16)
        g = arr[:, 1].astype(np.uint16)
        b = arr[:, 2].astype(np.uint16)
        rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
        # Big-endian byte pair per pixel
        high = ((rgb565 >> 8) & 0xFF).astype(np.uint8)
        low = (rgb565 & 0xFF).astype(np.uint8)
        interleaved = np.empty(len(high) * 2, dtype=np.uint8)
        interleaved[0::2] = high
        interleaved[1::2] = low
        return interleaved.tolist()

    @staticmethod
    def _rgb888_to_rgb565_python(raw_rgb: bytes) -> list[int]:
        """Pure-Python fallback for environments without numpy."""
        payload = bytearray((len(raw_rgb) // 3) * 2)
        out_i = 0
        for i in range(0, len(raw_rgb), 3):
            r = raw_rgb[i]
            g = raw_rgb[i + 1]
            b = raw_rgb[i + 2]
            rgb565 = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
            payload[out_i] = (rgb565 >> 8) & 0xFF
            payload[out_i + 1] = rgb565 & 0xFF
            out_i += 2
        return list(payload)

    def update(self):
        if self._board is None or self._surface is None:
            return
        try:
            raw_rgb = pygame.image.tostring(self._surface, "RGB")
            if self._board.previous_frame == raw_rgb:
                return
            if _HAS_NUMPY and self._board.previous_frame is not None:
                self._update_dirty_bands(raw_rgb)
            else:
                payload = self._rgb888_to_rgb565(raw_rgb)
                self._board.draw_image(0, 0, self.WIDTH, self.HEIGHT, payload)
            self._board.previous_frame = raw_rgb
        except Exception as exc:
            logger.debug("st7789_update_failed error=%s", exc)

    def _update_dirty_bands(self, raw_rgb: bytes) -> None:
        """Push only changed rows to reduce SPI transfer and flicker."""
        row_bytes = self.WIDTH * 3
        cur = np.frombuffer(raw_rgb, dtype=np.uint8).reshape(self.HEIGHT, row_bytes)
        prev = np.frombuffer(self._board.previous_frame, dtype=np.uint8).reshape(self.HEIGHT, row_bytes)
        diff_mask = np.any(cur != prev, axis=1)
        if not np.any(diff_mask):
            return
        changed = np.where(diff_mask)[0]
        y_start = int(changed[0])
        y_end = int(changed[-1]) + 1
        band_rgb = cur[y_start:y_end].tobytes()
        payload = self._rgb888_to_rgb565(band_rgb)
        self._board.draw_image(0, y_start, self.WIDTH, y_end - y_start, payload)

    def display(self, frame):
        """Compatibility helper for callers that pass PIL images or raw RGB565 bytes."""
        if self._board is None:
            raise RuntimeError("WhisPlayBoard unavailable: call init() before display()")

        if hasattr(frame, "convert"):
            rgb = frame.convert("RGB").tobytes("raw", "RGB")
            payload = self._rgb888_to_rgb565(rgb)
        elif isinstance(frame, (bytes, bytearray)):
            payload = list(frame)
        else:
            raise TypeError("display(frame) expects PIL image or RGB565 byte payload")

        self._board.draw_image(0, 0, self.WIDTH, self.HEIGHT, payload)

    def set_brightness(self, level: int) -> None:
        if self._board is not None:
            self._board.set_backlight(level)

    def quit(self):
        pygame.quit()


def create_driver(board=None) -> DisplayDriver:
    mode = os.environ.get("BITOS_DISPLAY", "pygame").lower()
    if mode == "st7789":
        return ST7789Driver(board=board)
    return PygameDriver()
