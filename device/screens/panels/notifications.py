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
from display.tokens import BLACK, DIM2, DIM3, HAIRLINE, PHYSICAL_H, PHYSICAL_W, WHITE, STATUS_BAR_H, ROW_H_MIN
from screens.base import BaseScreen
from screens.components import NavItem, VerticalNavController


class NotificationsPanel(BaseScreen):
    """Tiny-screen notifications placeholder with safe empty-state copy."""
    _owns_status_bar = True

    def __init__(self, on_back=None, ui_settings: dict | None = None):
        self._on_back = on_back
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)
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
            self._nav.move(1)
        elif action == "DOUBLE_PRESS":
            self._nav.activate_focused()
        elif action == "LONG_PRESS":
            self._go_back()
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

        # ── Status bar: inverted ──
        pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        title = self._font_small.render("NOTIFS", False, BLACK)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))

        # ── Content area ──
        content_y = STATUS_BAR_H + 4
        if self._error_copy:
            body = self._font_body.render(self._error_copy[:24], False, WHITE)
            surface.blit(body, (8, content_y + 8))
        elif not self._items:
            body = self._font_body.render("NO ALERTS", False, DIM2)
            surface.blit(body, (8, content_y + 8))
            sub = self._font_small.render("PRESS REFRESH", False, DIM3)
            surface.blit(sub, (8, content_y + 22))
        else:
            y = content_y
            notif_line_step = self._font_body.get_height() + 4
            for item in self._items[:5]:
                line = self._font_body.render(item[:24], False, WHITE)
                surface.blit(line, (8, y))
                y += notif_line_step

        # ── Nav rows: 26px, inverted focus ──
        y = PHYSICAL_H - ROW_H_MIN * len(self._nav.items) - 14
        for idx, item in enumerate(self._nav.items):
            focused = idx == self._nav.focus_index
            if focused:
                pygame.draw.rect(surface, WHITE, pygame.Rect(0, y, PHYSICAL_W, ROW_H_MIN))
            row_color = BLACK if focused else WHITE
            status_color = BLACK if focused else DIM2
            indicator = "> " if focused else "- "
            row = self._font_body.render(indicator + item.label, False, row_color)
            status = self._font_small.render(item.status, False, status_color)
            text_y = y + (ROW_H_MIN - row.get_height()) // 2
            surface.blit(row, (4, text_y))
            surface.blit(status, (PHYSICAL_W - status.get_width() - 8, text_y + 2))
            if not focused:
                pygame.draw.line(surface, HAIRLINE, (0, y + ROW_H_MIN - 1), (PHYSICAL_W, y + ROW_H_MIN - 1))
            y += ROW_H_MIN

        # ── Key hint bar ──
        hint = self._font_hint.render("SHORT:NEXT \u00b7 DBL:SEL \u00b7 LONG:BACK", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))

    def set_error(self, copy: str):
        self._error_copy = copy

    def _refresh(self):
        # Placeholder local refresh behavior for shell stage.
        self._error_copy = ""

    def _go_back(self):
        if self._on_back:
            self._on_back()
