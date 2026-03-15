"""Sidebar component — 84px wide, white border-right, item list.

Matches bitos-nav-v2.html .sidebar specification.
"""

import pygame

from device.ui.fonts import get_font
from device.ui.font_sizes import SIDEBAR_ITEM

from device.ui.panels.base import WHITE, BLACK, GRAY_444, GRAY_AAA, GRAY_080808, GRAY_0A

SEP_COLOR = GRAY_0A

SIDEBAR_W = 84
ITEM_H = 28  # padding top+bottom + 12px font
FONT_SIZE = SIDEBAR_ITEM
PAD_X = 7
PAD_Y = 8

ITEMS = ["HOME", "CHAT", "TASKS", "SETTINGS", "FOCUS", "MAIL", "MSGS", "MUSIC", "HISTORY"]


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
                text_color = GRAY_444

            text_surf = font.render(label, False, text_color)
            # Clip text if wider than sidebar
            surface.blit(text_surf, (x + PAD_X, iy + PAD_Y))

            # Bottom separator (subtle)
            if not selected:
                pygame.draw.line(surface, SEP_COLOR,
                                 (x, iy + ITEM_H - 1),
                                 (x + SIDEBAR_W - 2, iy + ITEM_H - 1))

            iy += ITEM_H
