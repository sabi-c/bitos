"""Inline tool result banner for chat messages."""
from __future__ import annotations

import pygame

from display.theme import get_font
from display.tokens import DIM3, WHITE

ACCENT_W = 4
PAD_X = 6
PAD_Y = 3
FONT_SIZE = 10

TOOL_COLORS: dict[str, tuple[int, int, int]] = {
    "create_task": (160, 100, 220),
    "update_task": (160, 100, 220),
    "complete_task": (160, 100, 220),
    "schedule_reminder": (220, 80, 80),
    "create_event": (80, 180, 120),
    "update_event": (80, 180, 120),
    "homekit": (220, 160, 60),
    "send_message": (60, 130, 220),
}
DEFAULT_COLOR: tuple[int, int, int] = (100, 200, 200)


class ToolBanner:
    """Compact inline banner showing a tool result inside a chat message.

    Renders a dark background strip with a 4px colored accent bar on the
    left edge, a "+ Summary" line, and an optional detail line below.
    """

    def __init__(self, tool: str, summary: str, detail: str = ""):
        self.tool = tool
        self.summary = summary
        self.detail = detail

    @property
    def accent_color(self) -> tuple[int, int, int]:
        """Match tool name against TOOL_COLORS keys (substring match)."""
        tool_lower = self.tool.lower()
        for key, color in TOOL_COLORS.items():
            if key in tool_lower:
                return color
        return DEFAULT_COLOR

    def render(self, surface: pygame.Surface, y: int) -> int:
        """Render the banner at the given y position.

        Returns the total height consumed.
        """
        font = get_font(FONT_SIZE)
        line_h = font.get_height() + 2

        # Calculate height: summary line + optional detail line + padding
        lines = 1
        if self.detail:
            lines = 2
        total_h = PAD_Y * 2 + lines * line_h

        width = surface.get_width()

        # Dark background
        bg_rect = pygame.Rect(0, y, width, total_h)
        pygame.draw.rect(surface, (18, 18, 18), bg_rect)

        # Colored accent bar on left
        accent_rect = pygame.Rect(0, y, ACCENT_W, total_h)
        pygame.draw.rect(surface, self.accent_color, accent_rect)

        # Summary line: "+ Summary"
        summary_text = f"+ {self.summary}"
        summary_surf = font.render(summary_text, False, WHITE)
        surface.blit(summary_surf, (ACCENT_W + PAD_X, y + PAD_Y))

        # Detail line (dimmed)
        if self.detail:
            detail_surf = font.render(self.detail, False, DIM3)
            surface.blit(detail_surf, (ACCENT_W + PAD_X, y + PAD_Y + line_h))

        return total_h
