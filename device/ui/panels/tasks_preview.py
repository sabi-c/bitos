"""TasksPreviewPanel — preview panel for the TASKS sidebar item.

Top area shows TODAY header + top 3 tasks with checkbox-style bullets.
Bottom area has submenu items for task actions.
"""

from __future__ import annotations

import pygame

from device.display.theme import get_font
from device.display.tokens import WHITE, DIM2, DIM3, HAIRLINE
from device.ui.panels.base import PreviewPanel


TASKS_HEADER_H = 16
TASK_LINE_H = 18
MAX_TASKS = 3
TASKS_PAD_X = 6
TASKS_PAD_Y = 2
TASKS_FONT_SIZE = 8
HEADER_FONT_SIZE = 10

# Checkbox characters
CHECK_DONE = "\u25a0"   # ■
CHECK_PENDING = "\u25a1"  # □

TASK_ITEMS = [
    {"label": "VIEW ALL TASKS", "description": "Browse all tasks", "action": "view_tasks"},
    {"label": "ADD TASK", "description": "Create a new task", "action": "add_task"},
    {"label": "BACK", "description": "Return to sidebar", "action": "back"},
]


class TasksPreviewPanel(PreviewPanel):
    """Preview panel for TASKS sidebar item."""

    def __init__(self, on_action: callable, repository=None):
        super().__init__(items=TASK_ITEMS, on_action=on_action)
        self._repository = repository
        self._tasks: list[dict] | None = None

    def set_tasks(self, tasks: list[dict]) -> None:
        """Update task list. Each dict should have 'title' and optionally 'done'."""
        self._tasks = tasks

    def _get_tasks(self) -> list[dict]:
        """Return tasks for display."""
        if self._tasks is not None:
            return self._tasks[:MAX_TASKS]
        # Placeholder when no tasks are available
        return [
            {"title": "No tasks loaded", "done": False},
        ]

    def render(self, surface: pygame.Surface) -> None:
        w = surface.get_width()
        header_font = get_font(HEADER_FONT_SIZE)
        task_font = get_font(TASKS_FONT_SIZE)

        # ── TODAY header ──
        header_surf = header_font.render("TODAY", False, WHITE)
        surface.blit(header_surf, (TASKS_PAD_X, TASKS_PAD_Y))

        # ── Task items ──
        tasks = self._get_tasks()
        y = TASKS_HEADER_H
        for task in tasks:
            if y + TASK_LINE_H > surface.get_height():
                break
            done = task.get("done", False)
            checkbox = CHECK_DONE if done else CHECK_PENDING
            color = DIM3 if done else DIM2
            title = task.get("title", "")
            if len(title) > 22:
                title = title[:19] + "..."
            text = f"{checkbox} {title}"
            surf = task_font.render(text, False, color)
            surface.blit(surf, (TASKS_PAD_X, y + TASKS_PAD_Y))
            y += TASK_LINE_H

        # Separator
        sep_y = TASKS_HEADER_H + MAX_TASKS * TASK_LINE_H
        pygame.draw.line(surface, HAIRLINE,
                         (TASKS_PAD_X, sep_y),
                         (w - TASKS_PAD_X, sep_y))

        # ── Submenu items ──
        self._render_items(surface, y_offset=sep_y + 2)
