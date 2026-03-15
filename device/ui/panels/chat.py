"""Chat panel — AI status dashboard, actions.

Renders into 156x280 right-panel surface.
Matches bitos-nav-v2.html .chat-panel specification.
"""

import pygame

from device.ui.fonts import get_font
from device.ui.font_sizes import BODY, CAPTION
from device.ui.panels.base import (
    BasePanel, PANEL_W, BLACK, WHITE, GRAY_555, GRAY_333, GRAY_444,
    GRAY_AAA, GRAY_1A, SEP_COLOR,
)

GREEN = (0, 255, 0)
YELLOW = (255, 255, 0)


class ChatPanel(BasePanel):
    TITLE = "CHAT"

    def __init__(self):
        self.model = "SONNET 4.6"
        self.context_pct = 84
        self.session_cost = "$0.84"
        self.context_used = "8.4K"
        self.context_max = "10K"
        self.online = True
        self.actions = [
            {"label": "NEW CHAT", "key": "newchat"},
            {"label": "PREVIOUS SESSION", "key": "previous"},
            {"label": "ALL HISTORY", "key": "history"},
        ]
        self.focused_action = 0

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(BLACK)

        # Header with online status
        y = self.draw_header(surface, right_text="ONLINE" if self.online else "OFFLINE",
                             right_color=GREEN if self.online else WHITE)

        font_body = get_font(BODY)
        font_cap = get_font(CAPTION)

        # Stat rows
        stats = [
            ("MODEL", self.model, WHITE),
            ("CONTEXT", f"{self.context_pct}%", YELLOW if self.context_pct > 80 else WHITE),
            ("SESSION", self.session_cost, WHITE),
        ]
        row_h = 24
        for label, value, val_color in stats:
            label_surf = font_body.render(label, False, GRAY_AAA)
            val_surf = font_body.render(value, False, val_color)
            surface.blit(label_surf, (8, y + (row_h - label_surf.get_height()) // 2))
            surface.blit(val_surf, (PANEL_W - val_surf.get_width() - 8,
                                    y + (row_h - val_surf.get_height()) // 2))
            pygame.draw.line(surface, SEP_COLOR, (0, y + row_h - 1), (PANEL_W, y + row_h - 1))
            y += row_h

        # Context bar
        bar_pad = 8
        bar_y = y + 6
        ctx_label = font_cap.render("CONTEXT", False, GRAY_333)
        surface.blit(ctx_label, (bar_pad, bar_y))
        bar_y += ctx_label.get_height() + 3

        # Bar outline
        bar_x = bar_pad
        bar_w = PANEL_W - bar_pad * 2
        bar_h = 5
        pygame.draw.rect(surface, WHITE, (bar_x, bar_y, bar_w, bar_h), 1)
        # Fill
        fill_w = int((bar_w - 2) * self.context_pct / 100)
        if fill_w > 0:
            pygame.draw.rect(surface, WHITE, (bar_x + 1, bar_y + 1, fill_w, bar_h - 2))

        # Scale labels
        bar_y += bar_h + 2
        zero_surf = font_cap.render("0", False, GRAY_1A)
        max_surf = font_cap.render(f"{self.context_used} / {self.context_max}", False, GRAY_1A)
        surface.blit(zero_surf, (bar_pad, bar_y))
        surface.blit(max_surf, (PANEL_W - max_surf.get_width() - bar_pad, bar_y))

        y = bar_y + max_surf.get_height() + 6
        pygame.draw.line(surface, SEP_COLOR, (0, y), (PANEL_W, y))
        y += 1

        # Action rows
        for idx, action in enumerate(self.actions):
            y = self.draw_action_row(surface, y, action["label"],
                                     focused=(idx == self.focused_action))
