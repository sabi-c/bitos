"""Status bar component — 18px height, white bg, black text.

Matches bitos-nav-v2.html .sbar specification.
"""

from datetime import datetime

import pygame

from device.ui.fonts import get_font
from device.ui.font_sizes import STATUS_BAR

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)

BAR_H = 20
FONT_SIZE = STATUS_BAR
PAD_X = 6


class StatusBar:
    """Renders the 18px status bar. Render-only."""

    def __init__(self):
        self.title = "BITOS"
        self.status_text = "AI\u00b7RDY"

    def render(self, surface: pygame.Surface, y: int = 0, width: int = 240) -> None:
        """Draw status bar at y position across full width."""
        font = get_font(FONT_SIZE)

        # White background
        pygame.draw.rect(surface, WHITE, (0, y, width, BAR_H))

        # Time (left)
        now = datetime.now()
        time_str = now.strftime("%I:%M").lstrip("0")
        time_surf = font.render(time_str, False, BLACK)
        surface.blit(time_surf, (PAD_X, y + (BAR_H - time_surf.get_height()) // 2))

        # Title (center)
        title_surf = font.render(self.title, False, BLACK)
        surface.blit(title_surf, ((width - title_surf.get_width()) // 2,
                                   y + (BAR_H - title_surf.get_height()) // 2))

        # Status (right)
        status_surf = font.render(self.status_text, False, BLACK)
        surface.blit(status_surf, (width - status_surf.get_width() - PAD_X,
                                    y + (BAR_H - status_surf.get_height()) // 2))

        # Bottom border
        pygame.draw.line(surface, WHITE, (0, y + BAR_H - 1), (width, y + BAR_H - 1), 2)
