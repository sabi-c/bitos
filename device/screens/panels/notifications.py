# SPRINT: P4-002 — Build notifications/settings screen shells and route from Home
# READS:  docs/planning/TASK_TRACKER.md, docs/planning/HANDOFF_NEXT_AGENT.md,
#         device/screens/panels/home.py, device/main.py, web_preview/server.py,
#         tests/test_phase2_shell_flow.py
# WRITES: device/screens/panels/notifications.py, device/screens/panels/settings.py,
#         device/screens/panels/home.py, device/main.py, web_preview/server.py,
#         tests/test_phase2_shell_flow.py, tests/test_panel_shells.py,
#         docs/planning/TASK_TRACKER.md, docs/planning/HANDOFF_NEXT_AGENT.md, README.md
# TESTS:  tests/test_panel_shells.py, tests/test_phase2_shell_flow.py
"""BITOS Notifications panel shell (Phase 4)."""
from __future__ import annotations

import pygame

from display.theme import load_ui_font, merge_runtime_ui_settings
from display.tokens import BLACK, DIM2, DIM3, HAIRLINE, PHYSICAL_H, PHYSICAL_W, WHITE
from screens.base import BaseScreen
from screens.components import NavItem, VerticalNavController


class NotificationsPanel(BaseScreen):
    """Tiny-screen notifications placeholder with safe empty-state copy."""

    def __init__(self, on_back=None, ui_settings: dict | None = None):
        self._on_back = on_back
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._items: list[str] = []
        self._error_copy = ""

        self._nav = VerticalNavController(
            [
                NavItem(key="refresh", label="REFRESH", status="LOCAL", action=self._refresh),
                NavItem(key="back", label="BACK", status="HOME", action=self._go_back),
            ]
        )

    def handle_action(self, action: str):
        if action == "SHORT_PRESS":
            self._nav.activate_focused()
        elif action in {"DOUBLE_PRESS", "LONG_PRESS"}:
            self._nav.move(1)
        elif action == "TRIPLE_PRESS":
            self._nav.move(-1)

    def handle_input(self, event: pygame.event.Event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_RETURN, pygame.K_SPACE):
            self._nav.activate_focused()
        elif event.key in (pygame.K_DOWN, pygame.K_j):
            self._nav.move(1)
        elif event.key in (pygame.K_UP, pygame.K_k):
            self._nav.move(-1)

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        title = self._font_title.render("NOTIFS", False, WHITE)
        surface.blit(title, (8, 8))
        pygame.draw.line(surface, HAIRLINE, (0, 24), (PHYSICAL_W, 24))

        if self._error_copy:
            body = self._font_body.render(self._error_copy[:24], False, WHITE)
            surface.blit(body, (8, 48))
        elif not self._items:
            body = self._font_body.render("NO ALERTS", False, DIM2)
            surface.blit(body, (8, 48))
            sub = self._font_small.render("PRESS REFRESH", False, DIM3)
            surface.blit(sub, (8, 62))
        else:
            y = 48
            for item in self._items[:5]:
                line = self._font_body.render(item[:24], False, WHITE)
                surface.blit(line, (8, y))
                y += 14

        y = PHYSICAL_H - 54
        for idx, item in enumerate(self._nav.items):
            row = self._font_body.render(item.label, False, WHITE)
            status = self._font_small.render(item.status, False, DIM2)
            if idx == self._nav.focus_index:
                pygame.draw.rect(surface, WHITE, pygame.Rect(4, y - 2, PHYSICAL_W - 8, 15), width=1)
            surface.blit(row, (8, y))
            surface.blit(status, (PHYSICAL_W - status.get_width() - 8, y + 2))
            y += 20

    def set_error(self, copy: str):
        self._error_copy = copy

    def _refresh(self):
        # Placeholder local refresh behavior for shell stage.
        self._error_copy = ""

    def _go_back(self):
        if self._on_back:
            self._on_back()
