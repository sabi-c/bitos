import pygame
from functools import lru_cache

FONT_PATH = "assets/fonts/PressStart2P-Regular.ttf"


@lru_cache(maxsize=32)
def get_font(size: int) -> pygame.font.Font:
    try:
        return pygame.font.Font(FONT_PATH, size)
    except Exception:
        return pygame.font.SysFont("monospace", size)
