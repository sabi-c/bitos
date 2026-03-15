"""Settings panel — list of setting rows with values.

Renders into 156x280 right-panel surface.
Matches bitos-nav-v2.html .settings-panel specification.
"""

import pygame

from device.ui.fonts import get_font
from device.ui.panels.base import (
    BasePanel, PANEL_W, BLACK, WHITE, GRAY_555, GRAY_333,
    GRAY_1A, SEP_COLOR,
)


class SettingsPanel(BasePanel):
    TITLE = "SETTINGS"

    def __init__(self):
        self.rows = [
            {"label": "AI MODEL", "value": "SONNET \u203a"},
            {"label": "AGENT MODE", "value": "PRODUCER \u203a"},
            {"label": "WEB SEARCH", "value": None, "toggle": True},
            {"label": "MEMORY", "value": None, "toggle": True},
            {"label": "WI-FI", "value": "STUDIO \u203a"},
            {"label": "BLUETOOTH", "value": "3 DEV \u203a"},
            {"label": "STORAGE", "value": "89/128G \u203a"},
            {"label": "ABOUT", "value": "v1.0 \u203a"},
        ]
        self.focused_row = 0

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(BLACK)

        y = self.draw_header(surface)

        font_7 = get_font(7)
        font_6 = get_font(6)

        row_h = 24
        for idx, row in enumerate(self.rows):
            focused = idx == self.focused_row
            if focused:
                pygame.draw.rect(surface, WHITE, (0, y, PANEL_W, row_h))

            text_color = BLACK if focused else GRAY_555
            label_surf = font_7.render(row["label"], False, text_color)
            ty = y + (row_h - label_surf.get_height()) // 2
            surface.blit(label_surf, (8, ty))

            if row.get("toggle"):
                # Toggle switch: 20x10 box with 6x6 knob
                sw_x = PANEL_W - 8 - 20
                sw_y = y + (row_h - 10) // 2
                border_color = BLACK if focused else WHITE
                pygame.draw.rect(surface, border_color, (sw_x, sw_y, 20, 10), 2)
                # Knob on right = ON
                knob_color = BLACK if focused else WHITE
                pygame.draw.rect(surface, knob_color, (sw_x + 20 - 1 - 6, sw_y + 1, 6, 6))
            elif row.get("value"):
                val_color = (102, 102, 102) if focused else GRAY_333
                val_surf = font_6.render(row["value"], False, val_color)
                surface.blit(val_surf, (PANEL_W - val_surf.get_width() - 8, ty))

            pygame.draw.line(surface, SEP_COLOR, (0, y + row_h - 1), (PANEL_W, y + row_h - 1))
            y += row_h
