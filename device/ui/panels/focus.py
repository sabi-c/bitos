"""Focus panel — timer display + action items.

Renders into 156x280 right-panel surface.
Matches bitos-nav-v2.html .focus-panel specification.
"""

import pygame

from device.ui.fonts import get_font
from device.ui.panels.base import (
    BasePanel, PANEL_W, BLACK, WHITE, GRAY_555, GRAY_333,
    GRAY_1A, SEP_COLOR,
)


class FocusPanel(BasePanel):
    TITLE = "FOCUS"

    def __init__(self):
        self.last_session_time = "25:00"
        self.session_type = "WORK"
        self.rounds = "1/4 ROUNDS"
        self.actions = [
            {"label": "START POMODORO", "key": "pomo"},
            {"label": "WORLD CLOCKS", "key": "clocks"},
            {"label": "STOPWATCH", "key": "stopwatch"},
        ]
        self.focused_action = 0

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(BLACK)

        y = self.draw_header(surface)

        font_8 = get_font(8)
        font_18 = get_font(18)
        font_5 = get_font(5)
        font_6 = get_font(6)
        font_7 = get_font(7)

        # Timer display area (bordered bottom)
        timer_area_h = 70
        timer_area_y = y

        # "LAST SESSION" label
        label_surf = font_8.render("LAST SESSION", False, GRAY_333)
        surface.blit(label_surf, ((PANEL_W - label_surf.get_width()) // 2,
                                   timer_area_y + 12))

        # Large timer
        timer_surf = font_18.render(self.last_session_time, False, WHITE)
        surface.blit(timer_surf, ((PANEL_W - timer_surf.get_width()) // 2,
                                   timer_area_y + 12 + label_surf.get_height() + 4))

        # Session info
        info_str = f"{self.session_type} \u00b7 {self.rounds}"
        info_surf = font_5.render(info_str, False, GRAY_555)
        surface.blit(info_surf, ((PANEL_W - info_surf.get_width()) // 2,
                                  timer_area_y + timer_area_h - info_surf.get_height() - 4))

        y = timer_area_y + timer_area_h
        # Bottom border of timer area
        pygame.draw.line(surface, WHITE, (0, y), (PANEL_W, y), 2)
        y += 2

        # Action rows
        action_h = 24
        for idx, action in enumerate(self.actions):
            focused = idx == self.focused_action
            if focused:
                pygame.draw.rect(surface, WHITE, (0, y, PANEL_W, action_h))

            text_color = BLACK if focused else GRAY_555
            arrow_surf = font_6.render("\u25b6", False, text_color)
            label_surf = font_7.render(action["label"], False, text_color)
            ty = y + (action_h - label_surf.get_height()) // 2
            surface.blit(arrow_surf, (8, ty))
            surface.blit(label_surf, (8 + arrow_surf.get_width() + 6, ty))

            pygame.draw.line(surface, SEP_COLOR, (0, y + action_h - 1), (PANEL_W, y + action_h - 1))
            y += action_h
