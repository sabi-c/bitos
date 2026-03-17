"""GenericPreviewPanel — simple submenu list for sidebar items without custom panels.

Used for HOME, SETTINGS, FOCUS, MAIL, MSGS, MUSIC, HISTORY.
"""

from __future__ import annotations

import pygame

from device.display.theme import get_font
from device.display.tokens import WHITE, HAIRLINE
from device.ui.panels.base import PreviewPanel


TITLE_FONT_SIZE = 10
TITLE_PAD_X = 6
TITLE_PAD_Y = 6
TITLE_H = 24


class GenericPreviewPanel(PreviewPanel):
    """Simple preview panel with a title, separator, and submenu items."""

    def __init__(self, label: str, items: list[dict], on_action: callable):
        super().__init__(items=items, on_action=on_action)
        self._label = label

    def render(self, surface: pygame.Surface) -> None:
        w = surface.get_width()
        # Title
        font = get_font(TITLE_FONT_SIZE)
        title_surf = font.render(self._label, False, WHITE)
        surface.blit(title_surf, (TITLE_PAD_X, TITLE_PAD_Y))

        # Separator between title and items
        sep_y = TITLE_H - 1
        pygame.draw.line(surface, HAIRLINE,
                         (TITLE_PAD_X, sep_y), (w - TITLE_PAD_X, sep_y))

        # Submenu items below title
        self._render_items(surface, y_offset=TITLE_H)
