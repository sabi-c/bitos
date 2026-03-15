"""Tasks panel — today's tasks + action items.

Renders into 156x280 right-panel surface.
Matches bitos-nav-v2.html .tasks-panel specification.
"""

import pygame

from device.ui.fonts import get_font
from device.ui.font_sizes import BODY, CAPTION
from device.ui.panels.base import (
    BasePanel, PANEL_W, BLACK, WHITE, GRAY_555, GRAY_333, GRAY_444,
    GRAY_111, GRAY_AAA, GRAY_1A, SEP_COLOR,
)


class TasksPanel(BasePanel):
    TITLE = "TASKS"

    def __init__(self):
        self.open_count = 5
        self.tasks = [
            {"text": "INVOICE JOAQUIN", "urgent": True},
            {"text": "TICKET FORMATTER", "urgent": True},
            {"text": "EL CAMINO BRAKES", "urgent": False},
        ]
        self.actions = [
            {"label": "TODAY'S TASKS", "key": "today"},
            {"label": "PROJECTS", "key": "projects"},
            {"label": "QUICK ADD (VOICE)", "key": "quickadd"},
        ]
        self.focused_action = 0

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(BLACK)

        # Header
        y = self.draw_header(surface, right_text=f"{self.open_count} OPEN",
                             right_color=GRAY_555)

        font_cap = get_font(CAPTION)
        font_body = get_font(BODY)

        # "TODAY" section header
        section_surf = font_cap.render("TODAY", False, GRAY_333)
        surface.blit(section_surf, (8, y + 5))
        y += section_surf.get_height() + 10
        pygame.draw.line(surface, SEP_COLOR, (0, y), (PANEL_W, y))
        y += 1

        # Task preview rows
        task_h = 24
        for task in self.tasks:
            # Dot
            dot_x = 8
            dot_y = y + (task_h - 4) // 2
            dot_color = (0xFF, 0x44, 0x44) if task.get("urgent") else GRAY_555
            pygame.draw.rect(surface, dot_color, (dot_x, dot_y, 4, 4))

            # Text
            text_surf = font_body.render(task["text"], False, GRAY_AAA)
            surface.blit(text_surf, (dot_x + 4 + 5, y + (task_h - text_surf.get_height()) // 2))

            pygame.draw.line(surface, SEP_COLOR, (0, y + task_h - 1), (PANEL_W, y + task_h - 1))
            y += task_h

        # "ACTIONS" section header
        pygame.draw.line(surface, GRAY_111, (0, y), (PANEL_W, y))
        y += 1
        section_surf = font_cap.render("ACTIONS", False, GRAY_333)
        surface.blit(section_surf, (8, y + 5))
        y += section_surf.get_height() + 10
        pygame.draw.line(surface, SEP_COLOR, (0, y), (PANEL_W, y))
        y += 1

        # Action rows
        for idx, action in enumerate(self.actions):
            y = self.draw_action_row(surface, y, action["label"],
                                     focused=(idx == self.focused_action))
