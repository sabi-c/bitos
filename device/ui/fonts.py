"""
BITOS Font Loader
Press Start 2P is the canonical BITOS font (pixel bitmap aesthetic).
Cached by size. Falls back to system monospace if TTF missing.
"""

from functools import lru_cache
import logging

import pygame

_FONT_PATHS = [
    "assets/fonts/PressStart2P-Regular.ttf",
    "/home/pi/bitos/assets/fonts/PressStart2P-Regular.ttf",
    "device/assets/fonts/PressStart2P.ttf",
]


@lru_cache(maxsize=32)
def get_font(size: int) -> pygame.font.Font:
    """Return Press Start 2P at given pixel size. Cached."""
    for path in _FONT_PATHS:
        try:
            return pygame.font.Font(path, size)
        except (FileNotFoundError, RuntimeError):
            continue
    logging.getLogger(__name__).warning("Press Start 2P TTF not found, using monospace")
    return pygame.font.SysFont("monospace", size)


def preload() -> None:
    """Pre-cache common sizes. Call once after pygame.font.init()."""
    pygame.font.init()
    for s in (5, 6, 7, 8, 9, 10, 12, 14, 20, 40):
        get_font(s)


def init_fonts() -> None:
    """Backward-compatible alias."""
    preload()
