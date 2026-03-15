"""Focus panel — timer display + action items.

Renders into 156x280 right-panel surface.
Matches bitos-nav-v2.html .focus-panel specification.
"""

import pygame

from device.ui.fonts import get_font
from device.ui.font_sizes import TIMER, BODY, CAPTION
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

        font_label = get_font(BODY)
        font_timer = get_font(TIMER)
        font_cap = get_font(CAPTION)
        font_body = get_font(BODY)

        # Timer display area (bordered bottom)
        timer_area_h = 70
        timer_area_y = y

        # "LAST SESSION" label
        label_surf = font_label.render("LAST SESSION", False, GRAY_333)
        surface.blit(label_surf, ((PANEL_W - label_surf.get_width()) // 2,
                                   timer_area_y + 12))

        # Large timer
        timer_surf = font_timer.render(self.last_session_time, False, WHITE)
        surface.blit(timer_surf, ((PANEL_W - timer_surf.get_width()) // 2,
                                   timer_area_y + 12 + label_surf.get_height() + 4))

        # Session info
        info_str = f"{self.session_type} \u00b7 {self.rounds}"
        info_surf = font_cap.render(info_str, False, GRAY_555)
        surface.blit(info_surf, ((PANEL_W - info_surf.get_width()) // 2,
                                  timer_area_y + timer_area_h - info_surf.get_height() - 4))

        y = timer_area_y + timer_area_h
        # Bottom border of timer area
        pygame.draw.line(surface, WHITE, (0, y), (PANEL_W, y), 2)
        y += 2

        # Action rows
        for idx, action in enumerate(self.actions):
            y = self.draw_action_row(surface, y, action["label"],
                                     focused=(idx == self.focused_action))
