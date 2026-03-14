"""
BITOS Display Driver
Abstract display interface + Pygame implementation for desktop development.
ST7789 hardware driver is a stub — will be ported from whisplay.py in Phase 5.
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
    # Whisplay HAT ST7789 LCD via SPI on Pi Zero 2W.
    # Only instantiated when BITOS_DISPLAY=st7789.
    """

    WIDTH = 240
    HEIGHT = 280

    # Pin assignments (BCM numbering)
    DC_PIN = 27  # GPIO27 = Board P13
    RST_PIN = 4  # GPIO4  = Board P7
    SPI_BUS = 0
    SPI_DEV = 0

    def __init__(self):
        self._spi = None
        self._gpio = None
        self._surface: pygame.Surface | None = None

    def init(self):
        try:
            import spidev
            import RPi.GPIO as GPIO  # type: ignore

            pygame.init()
            self._surface = pygame.Surface((self.WIDTH, self.HEIGHT))
            self._surface.fill(BLACK)

            self._gpio = GPIO
            self._spi = spidev.SpiDev()
            self._spi.open(self.SPI_BUS, self.SPI_DEV)
            self._spi.max_speed_hz = 40_000_000
            self._spi.mode = 0b11

            GPIO.setmode(GPIO.BCM)
            GPIO.setup(self.DC_PIN, GPIO.OUT)
            GPIO.setup(self.RST_PIN, GPIO.OUT)
            self._reset()
            self._init_display()
        except Exception as e:
            logger.error("st7789_init_failed", extra={"error": str(e)})
            raise

    def _reset(self):
        if self._gpio is None:
            return
        self._gpio.output(self.RST_PIN, self._gpio.HIGH)
        time.sleep(0.1)
        self._gpio.output(self.RST_PIN, self._gpio.LOW)
        time.sleep(0.1)
        self._gpio.output(self.RST_PIN, self._gpio.HIGH)
        time.sleep(0.1)

    def _init_display(self):
        # ST7789 init sequence for 240x280
        self._write_cmd(0x01)  # software reset
        time.sleep(0.15)
        self._write_cmd(0x11)  # sleep out
        time.sleep(0.5)
        self._write_cmd(0x3A, [0x05])  # pixel format RGB565
        self._write_cmd(0x36, [0x00])  # memory access control
        self._write_cmd(0x2A, [0x00, 0x00, 0x00, 0xEF])  # col addr 240
        self._write_cmd(0x2B, [0x00, 0x00, 0x01, 0x17])  # row addr 280
        self._write_cmd(0x21)  # invert on (Whisplay needs this)
        self._write_cmd(0x29)  # display on

    def _write_cmd(self, cmd: int, data: list[int] | None = None):
        if self._gpio is None or self._spi is None:
            return
        self._gpio.output(self.DC_PIN, self._gpio.LOW)
        self._spi.writebytes([cmd])
        if data:
            self._gpio.output(self.DC_PIN, self._gpio.HIGH)
            self._spi.writebytes(data)

    def get_surface(self) -> pygame.Surface:
        if self._surface is None:
            raise RuntimeError("ST7789 surface unavailable: call init() first")
        return self._surface

    def render(self, surface: pygame.Surface) -> None:
        """Convert pygame surface to RGB565 bytes and write to display."""
        if self._gpio is None or self._spi is None:
            return

        if surface.get_size() != (self.WIDTH, self.HEIGHT):
            surface = pygame.transform.scale(surface, (self.WIDTH, self.HEIGHT))

        raw = pygame.image.tostring(surface, "RGB")
        rgb565 = bytearray()
        for i in range(0, len(raw), 3):
            r, g, b = raw[i], raw[i + 1], raw[i + 2]
            rgb565.append((r & 0xF8) | (g >> 5))
            rgb565.append(((g & 0x1C) << 3) | (b >> 3))

        self._write_cmd(0x2C)
        self._gpio.output(self.DC_PIN, self._gpio.HIGH)

        chunk = 4096
        data = bytes(rgb565)
        for i in range(0, len(data), chunk):
            self._spi.writebytes(list(data[i : i + chunk]))

    def update(self):
        self.render(self.get_surface())

    def quit(self):
        try:
            if self._spi is not None:
                self._spi.close()
        finally:
            if self._gpio is not None:
                self._gpio.cleanup()
            pygame.quit()


def create_driver() -> DisplayDriver:
    """Factory: create the appropriate display driver based on environment."""
    mode = os.environ.get("BITOS_DISPLAY", "pygame").lower()
    if mode == "st7789":
        return ST7789Driver()
    else:
        return PygameDriver()
