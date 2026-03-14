"""
BITOS Display Driver
Abstract display interface + Pygame implementation for desktop development.
ST7789 hardware driver is a stub — will be ported from whisplay.py in Phase 5.
"""
import os
import sys
from abc import ABC, abstractmethod

import pygame

from display.tokens import (
    PHYSICAL_W, PHYSICAL_H, SCALE, WINDOW_W, WINDOW_H, BLACK, FPS
)


class DisplayDriver(ABC):
    """Abstract display interface."""

    @abstractmethod
    def init(self):
        """Initialize the display."""
        pass

    @abstractmethod
    def get_surface(self) -> pygame.Surface:
        """Return the internal rendering surface (240×280)."""
        pass

    @abstractmethod
    def update(self):
        """Push the internal surface to the actual display."""
        pass

    @abstractmethod
    def quit(self):
        """Clean up display resources."""
        pass


class PygameDriver(DisplayDriver):
    """Desktop simulator: renders 240×280 internal surface scaled 2× to a 480×560 window."""

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
        # Scale internal surface to window
        scaled = pygame.transform.scale(self._surface, (WINDOW_W, WINDOW_H))
        self._window.blit(scaled, (0, 0))
        pygame.display.flip()
        self._clock.tick(FPS)

    def quit(self):
        pygame.quit()

    def get_clock(self):
        return self._clock

    def capture_frame_bytes(self) -> bytes:
        """Capture current frame as JPEG bytes (for web preview)."""
        try:
            import io
            raw = pygame.image.tostring(self._surface, "RGB")
            from PIL import Image
            img = Image.frombytes("RGB", (PHYSICAL_W, PHYSICAL_H), raw)
            # Scale up for preview
            img = img.resize((WINDOW_W, WINDOW_H), Image.NEAREST)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            return buf.getvalue()
        except Exception:
            return b""


class ST7789Driver(DisplayDriver):
    """Hardware driver for Whisplay HAT ST7789 display.
    STUB — will port from whisplay-ai-chatbot/python/whisplay.py in Phase 5.
    """

    def init(self):
        raise NotImplementedError(
            "ST7789 driver not implemented yet. "
            "Run with BITOS_DISPLAY=pygame for desktop development."
        )

    def get_surface(self) -> pygame.Surface:
        raise NotImplementedError

    def update(self):
        raise NotImplementedError

    def quit(self):
        pass


def create_driver() -> DisplayDriver:
    """Factory: create the appropriate display driver based on environment."""
    mode = os.environ.get("BITOS_DISPLAY", "pygame").lower()
    if mode == "st7789":
        return ST7789Driver()
    else:
        return PygameDriver()
