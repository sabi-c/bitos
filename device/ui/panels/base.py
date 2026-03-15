"""Base class for right-panel renderers.

Each panel receives a 156x280 surface (the area right of the 84px sidebar).
It draws a panel header + body content. No navigation logic lives here.
"""

import pygame

from device.ui.fonts import get_font

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY_555 = (85, 85, 85)  # #555
GRAY_333 = (51, 51, 51)  # #333
GRAY_444 = (68, 68, 68)  # #444
GRAY_AAA = (170, 170, 170)  # #aaa
GRAY_1A = (26, 26, 26)  # #0a0a0a separator
GRAY_222 = (34, 34, 34)  # #222

# Panel dimensions (right of sidebar)
PANEL_W = 156
PANEL_H = 280

# Panel header
HDR_H = 16  # white header strip height
HDR_FONT_SIZE = 7
HDR_PAD_X = 8
HDR_PAD_Y = 5

# Separator
SEP_COLOR = GRAY_1A


class BasePanel:
    """Render-only base for right-side panels."""

    TITLE: str = ""

    def render(self, surface: pygame.Surface) -> None:
        """Draw panel content onto a 156x280 surface."""
        raise NotImplementedError

    def draw_header(self, surface: pygame.Surface, title: str | None = None,
                    right_text: str = "", right_color=None) -> int:
        """Draw white header strip. Returns y position after header."""
        t = title or self.TITLE
        font = get_font(HDR_FONT_SIZE)

        # White header background
        pygame.draw.rect(surface, WHITE, (0, 0, PANEL_W, HDR_H))
        # Bottom border
        pygame.draw.line(surface, WHITE, (0, HDR_H), (PANEL_W, HDR_H), 2)

        # Title text
        title_surf = font.render(t, False, BLACK)
        surface.blit(title_surf, (HDR_PAD_X, HDR_PAD_Y))

        # Optional right-side text
        if right_text:
            rc = right_color or GRAY_555
            right_surf = get_font(6).render(right_text, False, rc)
            surface.blit(right_surf, (PANEL_W - right_surf.get_width() - HDR_PAD_X, HDR_PAD_Y + 1))

        return HDR_H + 2  # 2px border

    def draw_separator(self, surface: pygame.Surface, y: int) -> None:
        """Draw a subtle horizontal separator."""
        pygame.draw.line(surface, SEP_COLOR, (0, y), (PANEL_W, y))
