"""Hint bar component — bottom key hints.

Matches bitos-nav-v2.html .kh specification.
"""

import pygame

from display.theme import get_font
from display.tokens import FONT_SIZE_HINT, GRAY_11, GRAY_0A

SEP_COLOR = GRAY_0A

FONT_SIZE = FONT_SIZE_HINT  # 8px, lowest acceptable size on 218 PPI
PAD_X = 6
PAD_Y = 2
DEFAULT_HINT = "SHORT:NEXT \u00b7 DBL:SELECT \u00b7 LONG:BACK"


class HintBar:
    """Renders the bottom key hint bar. Render-only."""

    def __init__(self):
        self.text = DEFAULT_HINT

    def render(self, surface: pygame.Surface, y: int, width: int = 240) -> None:
        """Draw hint bar at y position across full width."""
        font = get_font(FONT_SIZE)

        # Top separator
        pygame.draw.line(surface, SEP_COLOR, (0, y), (width, y))

        # Text centered
        hint_surf = font.render(self.text, False, GRAY_11)
        surface.blit(hint_surf, ((width - hint_surf.get_width()) // 2, y + PAD_Y))
