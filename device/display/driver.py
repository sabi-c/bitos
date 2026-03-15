"""
BITOS Display Driver
Abstract display interface + Pygame implementation for desktop development.
ST7789 hardware driver delegates to WhisPlayBoard which owns all HAT GPIO.
"""
import logging
import os
from abc import ABC, abstractmethod

import pygame

from display.tokens import (
    PHYSICAL_W, PHYSICAL_H, SCALE, WINDOW_W, WINDOW_H, BLACK, FPS
)

logger = logging.getLogger(__name__)


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
    """
    # WHY THIS EXISTS: renders Pygame surface to physical
    # Whisplay HAT ST7789 LCD via WhisPlayBoard.
    # WhisPlayBoard owns all HAT GPIO (SPI, button, backlight, LED).
    # Only instantiated when BITOS_DISPLAY=st7789.
    """

    WIDTH = 240
    HEIGHT = 280

    def __init__(self):
        self._surface: pygame.Surface | None = None
        self._board = None

    def init(self):
        from hardware.whisplay_board import get_board

        self._board = get_board()
        if self._board is None:
            raise RuntimeError("WhisPlayBoard unavailable: get_board() returned None; cannot initialize ST7789 display")

        pygame.init()
        self._surface = pygame.Surface((self.WIDTH, self.HEIGHT))
        self._surface.fill(BLACK)

        from PIL import Image as PILImage
        black_image = PILImage.new("RGB", (self.WIDTH, self.HEIGHT), (0, 0, 0))
        self._board.disp.image(black_image)
        self._board.set_backlight(100)

    def get_surface(self) -> pygame.Surface:
        if self._surface is None:
            raise RuntimeError("ST7789 surface unavailable: call init() first")
        return self._surface

    def update(self):
        """Convert pygame surface to PIL Image and push to board.disp."""
        if self._board is None or self._surface is None:
            return
        try:
            from PIL import Image as PILImage
            raw = pygame.image.tostring(self._surface, "RGB")
            img = PILImage.frombytes("RGB", (self.WIDTH, self.HEIGHT), raw)
            self.display(img)
        except Exception as e:
            logger.debug("st7789_update_failed", extra={"error": str(e)})

    def display(self, frame):
        if self._board is None:
            raise RuntimeError("WhisPlayBoard unavailable: call init() before display()")
        self._board.disp.image(frame)

    def set_brightness(self, level: int) -> None:
        """Set backlight level 0–100."""
        if self._board is not None:
            self._board.set_backlight(level)

    def quit(self):
        pygame.quit()



def create_driver() -> DisplayDriver:
    """Factory: create the appropriate display driver based on environment."""
    mode = os.environ.get("BITOS_DISPLAY", "pygame").lower()
    if mode == "st7789":
        return ST7789Driver()
    else:
        return PygameDriver()
