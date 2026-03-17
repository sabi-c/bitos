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

ITEMS = ["HOME", "CHAT", "TASKS", "ACTIVITY", "COMMS", "FILES", "RECORD", "SETTINGS", "FOCUS"]


class Sidebar:
    """Renders the 84px sidebar. Render-only, no input handling."""

    def __init__(self):
        self.selected_index = 0
        self.items = list(ITEMS)

    def render(self, surface: pygame.Surface, x: int = 0, y: int = 0, height: int = 280,
               highlight_y_offset: float = 0.0) -> None:
        """Draw sidebar onto surface at (x, y) with given height.

        Args:
            highlight_y_offset: Pixel offset for the selection highlight during
                smooth scroll animation. 0.0 when no animation is active.
        """
        font = get_font(FONT_SIZE)

        # Background
        pygame.draw.rect(surface, BLACK, (x, y, SIDEBAR_W, height))

        # Right border (2px white)
        pygame.draw.line(surface, WHITE, (x + SIDEBAR_W - 1, y),
                         (x + SIDEBAR_W - 1, y + height), 2)

        # Items — render non-selected items first, then selected on top
        safe_selected = self.selected_index % len(self.items) if self.items else -1

        # First pass: non-selected items
        iy = y
        for idx, label in enumerate(self.items):
            if iy + ITEM_H > y + height:
                break
            if idx != safe_selected:
                text_surf = font.render(label, False, GRAY_44)
                surface.blit(text_surf, (x + PAD_X, iy + PAD_Y))
                # Bottom separator (subtle)
                pygame.draw.line(surface, SEP_COLOR,
                                 (x, iy + ITEM_H - 1),
                                 (x + SIDEBAR_W - 2, iy + ITEM_H - 1))
            iy += ITEM_H

        # Second pass: selected item with smooth scroll offset
        if safe_selected >= 0 and safe_selected < len(self.items):
            sel_y = y + safe_selected * ITEM_H + int(highlight_y_offset)
            # Clamp to visible area
            sel_y = max(y, min(sel_y, y + height - ITEM_H))
            # White highlight background
            pygame.draw.rect(surface, WHITE, (x, sel_y, SIDEBAR_W - 2, ITEM_H))
            text_surf = font.render(self.items[safe_selected], False, BLACK)
            surface.blit(text_surf, (x + PAD_X, sel_y + PAD_Y))
