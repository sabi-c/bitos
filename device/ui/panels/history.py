"""History panel — recent chat sessions list.

Renders into 156x280 right-panel surface.
Matches bitos-nav-v2.html .history-panel specification.
"""

import pygame

from device.ui.fonts import get_font
from device.ui.font_sizes import BODY, CAPTION
from device.ui.panels.base import (
    BasePanel, PANEL_W, BLACK, WHITE, GRAY_555, GRAY_333,
    GRAY_666, GRAY_AAA, GRAY_1A, SEP_COLOR,
)


class HistoryPanel(BasePanel):
    TITLE = "HISTORY"

    def __init__(self):
        self.total_count = 12
        self.sessions = [
            {"title": "SSS TASK STATUS", "meta": "TODAY 09:44"},
            {"title": "EL CAMINO REPAIR", "meta": "TODAY 07:20"},
            {"title": "TENDER FEST IDEAS", "meta": "YESTERDAY"},
            {"title": "OBSIDIAN MCP SETUP", "meta": "2 DAYS AGO"},
            {"title": "CLOWN WAITER BIT", "meta": "3 DAYS AGO"},
            {"title": "LUNA LUNA DECK", "meta": "5 DAYS AGO"},
        ]
        self.focused_session = 0

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(BLACK)

        # Header
        y = self.draw_header(surface, right_text=str(self.total_count),
                             right_color=GRAY_555)

        font_body = get_font(BODY)
        font_cap = get_font(CAPTION)

        # Session rows
        row_h = 28
        for idx, session in enumerate(self.sessions):
            focused = idx == self.focused_session

            if focused:
                pygame.draw.rect(surface, WHITE, (0, y, PANEL_W, row_h))

            # Title
            title_color = BLACK if focused else GRAY_AAA
            title_surf = font_body.render(session["title"][:18], False, title_color)
            surface.blit(title_surf, (8, y + 4))

            # Meta (timestamp)
            meta_color = GRAY_666 if focused else GRAY_333
            meta_surf = font_cap.render(session["meta"], False, meta_color)
            surface.blit(meta_surf, (8, y + 4 + title_surf.get_height() + 2))

            pygame.draw.line(surface, SEP_COLOR, (0, y + row_h - 1), (PANEL_W, y + row_h - 1))
            y += row_h
