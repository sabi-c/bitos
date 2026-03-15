"""Messages panel — SMS/message threads with avatars.

Renders into 156x280 right-panel surface.
Matches bitos-nav-v2.html .msgs-panel specification.
"""

import pygame

from device.ui.fonts import get_font
from device.ui.panels.base import (
    BasePanel, PANEL_W, BLACK, WHITE, GRAY_555, GRAY_333,
    GRAY_AAA, GRAY_1A, SEP_COLOR, GRAY_222,
)


class MessagesPanel(BasePanel):
    TITLE = "MESSAGES"

    def __init__(self):
        self.unread_count = 2
        self.threads = [
            {"initials": "JQ", "name": "JOAQUIN",
             "preview": "Can you call me re: overtime rate?",
             "unread": True},
            {"initials": "AN", "name": "ANTHONY",
             "preview": "Yo did you fix the El Camino lol",
             "unread": True},
            {"initials": "BW", "name": "BEN W.",
             "preview": "Casting went great. Debrief Fri?",
             "unread": False},
        ]
        self.focused_thread = 0

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(BLACK)

        font_7 = get_font(7)
        font_5 = get_font(5)

        # Header with badge
        pygame.draw.rect(surface, WHITE, (0, 0, PANEL_W, 16))
        pygame.draw.line(surface, WHITE, (0, 16), (PANEL_W, 16), 2)
        title_surf = font_7.render("MESSAGES", False, BLACK)
        surface.blit(title_surf, (8, 5))

        badge_text = str(self.unread_count)
        badge_surf = font_5.render(badge_text, False, BLACK)
        bx = 8 + title_surf.get_width() + 6
        by = 5
        pygame.draw.rect(surface, BLACK, (bx - 1, by - 1,
                                          badge_surf.get_width() + 8,
                                          badge_surf.get_height() + 4), 2)
        surface.blit(badge_surf, (bx + 3, by + 1))

        y = 18

        # Message rows
        row_h = 36
        for idx, thread in enumerate(self.threads):
            focused = idx == self.focused_thread
            unread = thread.get("unread", False)

            if focused:
                pygame.draw.rect(surface, WHITE, (0, y, PANEL_W, row_h))

            # Avatar box (24x24)
            av_x = 8
            av_y = y + (row_h - 24) // 2
            border_color = BLACK if focused else GRAY_333
            pygame.draw.rect(surface, border_color, (av_x, av_y, 24, 24), 2)
            av_font = font_7
            av_surf = av_font.render(thread["initials"], False,
                                     BLACK if focused else WHITE)
            surface.blit(av_surf, (av_x + (24 - av_surf.get_width()) // 2,
                                   av_y + (24 - av_surf.get_height()) // 2))

            # Name
            text_x = av_x + 24 + 6
            if focused:
                name_color = BLACK
            elif unread:
                name_color = WHITE
            else:
                name_color = GRAY_AAA

            name_surf = font_7.render(thread["name"], False, name_color)
            surface.blit(name_surf, (text_x, y + 6))

            # Preview
            preview_color = BLACK if focused else GRAY_333
            preview_text = thread["preview"][:18]
            preview_surf = font_5.render(preview_text, False, preview_color)
            surface.blit(preview_surf, (text_x, y + 6 + name_surf.get_height() + 3))

            pygame.draw.line(surface, SEP_COLOR, (0, y + row_h - 1), (PANEL_W, y + row_h - 1))
            y += row_h

        # "NEW MESSAGE" footer
        pygame.draw.line(surface, GRAY_333, (0, y), (PANEL_W, y), 2)
        y += 2
        footer_surf = font_5.render("\u25b6 NEW MESSAGE", False, GRAY_222)
        surface.blit(footer_surf, (8, y + 6))
