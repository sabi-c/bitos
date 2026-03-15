"""
Font loader for BITOS. Caches fonts by size.
Press Start 2P is the canonical BITOS font.
"""
import os
from functools import lru_cache

import pygame

FONT_CANDIDATES = [
    "assets/fonts/PressStart2P-Regular.ttf",
    "device/assets/fonts/PressStart2P.ttf",
    "/usr/share/fonts/truetype/press-start-2p/PressStart2P-Regular.ttf",
]
_FALLBACK = None


def _font_path() -> str | None:
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


@lru_cache(maxsize=32)
def get_font(size: int) -> pygame.font.Font:
    """Get Press Start 2P at given pixel size. Cached."""
    path = _font_path()
    if path:
        try:
            return pygame.font.Font(path, size)
        except (FileNotFoundError, RuntimeError):
            pass

    global _FALLBACK
    if _FALLBACK is None:
        _FALLBACK = pygame.font.SysFont("monospace", size)
    return pygame.font.SysFont("monospace", size)


def init_fonts() -> None:
    """Call once after pygame.init()."""
    pygame.font.init()
    for s in [5, 6, 7, 8, 9, 12, 14, 20, 40, 42]:
        get_font(s)
