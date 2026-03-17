"""Status bar component — 20px height, white bg, black text.

Matches bitos-nav-v2.html .sbar specification.
Shows: time (left) | breadcrumb (center) | status + notification badge (right).
"""

import math
from datetime import datetime

import pygame

from display.theme import get_font
from display.tokens import FONT_SIZE_STATUS_BAR, WHITE, BLACK, HAIRLINE

BAR_H = 20
FONT_SIZE = FONT_SIZE_STATUS_BAR
PAD_X = 6

# Notification badge
BADGE_COLOR = BLACK
BADGE_RADIUS = 5


class StatusBar:
    """Renders the 20px status bar with breadcrumb and notification badge."""

    def __init__(self):
        self.title = "BITOS"
        self.status_text = "AI\u00b7RDY"
        self.breadcrumb: str = ""
        self.unread_count: int = 0
        self._badge_pulse_time: float = 0.0
        self._badge_color: tuple = (255, 255, 255)

    def set_breadcrumb(self, crumb: str) -> None:
        """Set the center breadcrumb text (e.g. 'HOME' or 'HOME > CHAT')."""
        self.breadcrumb = crumb

    def set_unread_count(self, count: int, category: str = "") -> None:
        """Set unread notification count for the badge indicator."""
        self.unread_count = max(0, count)
        if count > 0:
            self._badge_pulse_time = 0.0
        if category:
            CATEGORY_COLORS = {
                "sms": (60, 130, 220), "mail": (180, 140, 60), "calendar": (80, 180, 120),
                "task": (160, 100, 220), "agent": (100, 200, 200), "reminder": (220, 80, 80),
                "system": (120, 120, 120),
            }
            self._badge_color = CATEGORY_COLORS.get(category, (255, 255, 255))

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

        # Breadcrumb or title (center)
        center_text = self.breadcrumb if self.breadcrumb else self.title
        center_surf = font.render(center_text, False, BLACK)
        surface.blit(center_surf, ((width - center_surf.get_width()) // 2,
                                    y + (BAR_H - center_surf.get_height()) // 2))

        # Status + notification badge (right)
        status_surf = font.render(self.status_text, False, BLACK)
        status_x = width - status_surf.get_width() - PAD_X
        status_y = y + (BAR_H - status_surf.get_height()) // 2
        surface.blit(status_surf, (status_x, status_y))

        # Notification badge dot (drawn left of status text)
        if self.unread_count > 0:
            self._badge_pulse_time += 1 / 15  # ~15 FPS tick
            alpha = int(200 + 55 * math.sin(self._badge_pulse_time * math.pi))
            alpha = max(0, min(255, alpha))
            r, g, b = self._badge_color
            pulse_color = (
                max(0, min(255, r * alpha // 255)),
                max(0, min(255, g * alpha // 255)),
                max(0, min(255, b * alpha // 255)),
            )
            badge_x = status_x - BADGE_RADIUS - 3
            badge_y = y + BAR_H // 2
            pygame.draw.circle(surface, pulse_color, (badge_x, badge_y), BADGE_RADIUS)
            # Draw count inside if small enough
            if self.unread_count <= 99:
                badge_font = get_font(FONT_SIZE - 4)
                count_str = str(self.unread_count)
                count_surf = badge_font.render(count_str, False, WHITE)
                surface.blit(count_surf, (badge_x - count_surf.get_width() // 2,
                                          badge_y - count_surf.get_height() // 2))

        # Bottom border
        pygame.draw.line(surface, BLACK, (0, y + BAR_H - 1), (width, y + BAR_H - 1), 1)
