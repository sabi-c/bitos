"""Sidebar component — 84px wide, white border-right, item list.

Matches bitos-nav-v2.html .sidebar specification.
"""

import pygame

from display.theme import get_font
from display.tokens import (
    WHITE, BLACK,
    GRAY_44, GRAY_AA, GRAY_08, GRAY_0A,
)

SEP_COLOR = GRAY_0A

SIDEBAR_W = 84
SIDEBAR_W_COLLAPSED = 28  # icon-only mode
ITEM_H = 20  # 20*10=200px fits in 208px available height
FONT_SIZE = 14  # bumped from 12 for readability
ICON_FONT_SIZE = 12
PAD_X = 7
PAD_Y = 3  # reduced to fit 10 items at larger font

ITEMS = ["HOME", "CHAT", "TASKS", "ACTIVITY", "COMMS", "FILES", "RECORD", "SETTINGS", "FOCUS"]

# Sidebar item icons (single-char symbols for collapsed mode)
ITEM_ICONS = {
    "HOME": "H",
    "CHAT": "C",
    "TASKS": "T",
    "ACTIVITY": "!",
    "COMMS": "M",
    "FILES": "F",
    "RECORD": "R",
    "SETTINGS": "S",
    "FOCUS": "Z",
}


class Sidebar:
    """Renders the 84px sidebar (or 28px collapsed). Render-only, no input handling."""

    def __init__(self):
        self.selected_index = 0
        self.items = list(ITEMS)
        self.collapsed = False  # True when in submenu — shows icons only

    @property
    def current_width(self) -> int:
        return SIDEBAR_W_COLLAPSED if self.collapsed else SIDEBAR_W

    def render(self, surface: pygame.Surface, x: int = 0, y: int = 0, height: int = 280,
               highlight_y_offset: float = 0.0) -> None:
        """Draw sidebar onto surface at (x, y) with given height.

        Args:
            highlight_y_offset: Pixel offset for the selection highlight during
                smooth scroll animation. 0.0 when no animation is active.
        """
        if self.collapsed:
            self._render_collapsed(surface, x, y, height)
            return

        font = get_font(FONT_SIZE)
        w = SIDEBAR_W

        # Background
        pygame.draw.rect(surface, BLACK, (x, y, w, height))

        # Right border (2px white)
        pygame.draw.line(surface, WHITE, (x + w - 1, y),
                         (x + w - 1, y + height), 2)

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
                                 (x + w - 2, iy + ITEM_H - 1))
            iy += ITEM_H

        # Second pass: selected item with smooth scroll offset
        if safe_selected >= 0 and safe_selected < len(self.items):
            sel_y = y + safe_selected * ITEM_H + int(highlight_y_offset)
            # Clamp to visible area
            sel_y = max(y, min(sel_y, y + height - ITEM_H))
            # White highlight background
            pygame.draw.rect(surface, WHITE, (x, sel_y, w - 2, ITEM_H))
            text_surf = font.render(self.items[safe_selected], False, BLACK)
            surface.blit(text_surf, (x + PAD_X, sel_y + PAD_Y))

    def _render_collapsed(self, surface: pygame.Surface, x: int, y: int, height: int) -> None:
        """Render narrow icon-only sidebar."""
        font = get_font(ICON_FONT_SIZE)
        w = SIDEBAR_W_COLLAPSED

        # Background
        pygame.draw.rect(surface, BLACK, (x, y, w, height))

        # Right border
        pygame.draw.line(surface, WHITE, (x + w - 1, y),
                         (x + w - 1, y + height), 2)

        safe_selected = self.selected_index % len(self.items) if self.items else -1

        iy = y
        for idx, label in enumerate(self.items):
            if iy + ITEM_H > y + height:
                break
            icon = ITEM_ICONS.get(label, label[0])
            if idx == safe_selected:
                # Highlight
                pygame.draw.rect(surface, WHITE, (x, iy, w - 2, ITEM_H))
                icon_surf = font.render(icon, False, BLACK)
            else:
                icon_surf = font.render(icon, False, GRAY_44)
            # Center icon in the narrow column
            ix = x + (w - 2 - icon_surf.get_width()) // 2
            surface.blit(icon_surf, (ix, iy + PAD_Y))
            iy += ITEM_H
