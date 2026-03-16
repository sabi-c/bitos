"""ActivityPreviewPanel — unified feed of notifications, agent tasks, messages.

Top area: unread counts summary (messages, emails, tasks).
Below: submenu items for different views.
"""

from __future__ import annotations

import pygame

from device.display.theme import get_font
from device.display.tokens import WHITE, DIM2, DIM3, HAIRLINE
from device.ui.panels.base import PreviewPanel


HEADER_H = 48
HEADER_FONT = 10
COUNT_FONT = 8
PAD_X = 6
PAD_Y = 4
LINE_H = 14

ACTIVITY_ITEMS = [
    {"label": "ALL ACTIVITY", "description": "Full activity feed", "action": "open"},
    {"label": "NOTIFICATIONS", "description": "View notifications", "action": "notifications"},
    {"label": "AGENT TASKS", "description": "Agent subtasks", "action": "agent_tasks"},
    {"label": "BACK", "description": "Return to sidebar", "action": "back"},
]


class ActivityPreviewPanel(PreviewPanel):
    """Preview panel for ACTIVITY sidebar item (merged agent + notifications)."""

    def __init__(self, on_action: callable):
        super().__init__(items=ACTIVITY_ITEMS, on_action=on_action)
        self._unread_msgs = 0
        self._unread_mail = 0
        self._pending_tasks = 0

    def set_counts(self, msgs: int = 0, mail: int = 0, tasks: int = 0) -> None:
        """Update unread/pending counts for the header."""
        self._unread_msgs = msgs
        self._unread_mail = mail
        self._pending_tasks = tasks

    def render(self, surface: pygame.Surface) -> None:
        w = surface.get_width()
        header_font = get_font(HEADER_FONT)
        count_font = get_font(COUNT_FONT)

        # ── Header: summary counts ──
        y = PAD_Y
        header_surf = header_font.render("ACTIVITY", False, WHITE)
        surface.blit(header_surf, (PAD_X, y))
        y += LINE_H + 2

        # Count lines
        counts = []
        if self._unread_msgs:
            counts.append(f"{self._unread_msgs} message{'s' if self._unread_msgs != 1 else ''}")
        if self._unread_mail:
            counts.append(f"{self._unread_mail} email{'s' if self._unread_mail != 1 else ''}")
        if self._pending_tasks:
            counts.append(f"{self._pending_tasks} task{'s' if self._pending_tasks != 1 else ''}")

        if counts:
            for line in counts[:2]:  # Max 2 lines in header
                surf = count_font.render(line, False, DIM2)
                surface.blit(surf, (PAD_X, y))
                y += LINE_H
        else:
            surf = count_font.render("All clear", False, DIM3)
            surface.blit(surf, (PAD_X, y))

        # Separator
        sep_y = HEADER_H - 1
        pygame.draw.line(surface, HAIRLINE,
                         (PAD_X, sep_y), (w - PAD_X, sep_y))

        # ── Submenu items ──
        self._render_items(surface, y_offset=HEADER_H)
