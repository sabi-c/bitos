"""Shared skeleton loading animation for list panels."""
import pygame

from display.tokens import DIM3, DIM4, HAIRLINE, PHYSICAL_W, ROW_H_MIN


def render_skeleton(surface: pygame.Surface, y: int, count: int = 4) -> None:
    """Render blinking skeleton loading rows."""
    blink = (pygame.time.get_ticks() // 800) % 2 == 0
    color = DIM3 if blink else DIM4
    for _ in range(count):
        pygame.draw.rect(surface, color, (8, y + 4, PHYSICAL_W - 48, 8))
        pygame.draw.rect(surface, HAIRLINE, (PHYSICAL_W - 36, y + 4, 28, 8))
        pygame.draw.line(surface, HAIRLINE, (0, y + ROW_H_MIN - 1), (PHYSICAL_W, y + ROW_H_MIN - 1))
        y += ROW_H_MIN
