"""Sidebar component — 84px wide, white border-right, item list.

Matches bitos-nav-v2.html .sidebar specification.
"""

import pygame

from device.display.theme import get_font
from device.display.tokens import (
    WHITE, BLACK,
    GRAY_44, GRAY_AA, GRAY_08, GRAY_0A,
)

SEP_COLOR = GRAY_0A

SIDEBAR_W = 84
ITEM_H = 20  # 20*10=200px fits in 208px available height
FONT_SIZE = 14  # bumped from 12 for readability
PAD_X = 7
PAD_Y = 3  # reduced to fit 10 items at larger font

ITEMS = ["HOME", "CHAT", "TASKS", "ACTIVITY", "COMMS", "FILES", "SETTINGS", "FOCUS"]


class Sidebar:
    """Renders the 84px sidebar. Render-only, no input handling."""

    def __init__(self):
        self.selected_index = 0
        self.items = list(ITEMS)

    def render(self, surface: pygame.Surface, x: int = 0, y: int = 0, height: int = 280) -> None:
        """Draw sidebar onto surface at (x, y) with given height."""
        font = get_font(FONT_SIZE)

        # Background
        pygame.draw.rect(surface, BLACK, (x, y, SIDEBAR_W, height))

        # Right border (2px white)
        pygame.draw.line(surface, WHITE, (x + SIDEBAR_W - 1, y),
                         (x + SIDEBAR_W - 1, y + height), 2)

        # Items
        iy = y
        for idx, label in enumerate(self.items):
            if iy + ITEM_H > y + height:
                break

            selected = idx == self.selected_index
            if selected:
                # Inverted: white bg, black text
                pygame.draw.rect(surface, WHITE, (x, iy, SIDEBAR_W - 2, ITEM_H))
                text_color = BLACK
            else:
                text_color = GRAY_44

            text_surf = font.render(label, False, text_color)
            # Clip text if wider than sidebar
            surface.blit(text_surf, (x + PAD_X, iy + PAD_Y))

            # Bottom separator (subtle)
            if not selected:
                pygame.draw.line(surface, SEP_COLOR,
                                 (x, iy + ITEM_H - 1),
                                 (x + SIDEBAR_W - 2, iy + ITEM_H - 1))

            iy += ITEM_H
