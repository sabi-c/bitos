"""Read-only integration detail screen."""
from __future__ import annotations

import pygame

from display.theme import load_ui_font, merge_runtime_ui_settings
from display.tokens import BLACK, DIM2, DIM3, HAIRLINE, PHYSICAL_H, PHYSICAL_W, WHITE, STATUS_BAR_H, ROW_H_MIN
from screens.base import BaseScreen


class IntegrationDetailPanel(BaseScreen):
    """Shows live status + config instructions for one integration."""

    def __init__(self, integration_name: str, status_data: dict | None = None, on_back=None, ui_settings: dict | None = None):
        self._integration_name = integration_name
        self._status_data = status_data or {}
        self._on_back = on_back
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)

    def handle_action(self, action: str):
        if action == "DOUBLE_PRESS" and self._on_back:
            self._on_back()

    def handle_input(self, event: pygame.event.Event):
        if event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            if self._on_back:
                self._on_back()

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)
        pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        top = self._font_small.render(f"● {self._integration_name.upper()}  84%", False, BLACK)
        surface.blit(top, (6, (STATUS_BAR_H - top.get_height()) // 2))

        y = STATUS_BAR_H + 4
        title = self._font_body.render(self._integration_name.upper(), False, WHITE)
        surface.blit(title, (8, y))
        y += ROW_H_MIN
        pygame.draw.line(surface, HAIRLINE, (8, y - 4), (PHYSICAL_W - 8, y - 4))

        status = str(self._status_data.get("status", "unknown")).upper()
        rows = [
            f"Status:  {status}",
            f"Server:  {self._status_data.get('server_url', '—')}",
            f"Unread:  {self._status_data.get('unread', 0)}",
            f"Last msg: {self._status_data.get('last_checked', 'never')}",
        ]
        for row in rows:
            r = self._font_small.render(row, False, DIM2)
            surface.blit(r, (8, y))
            y += ROW_H_MIN - 8

        y += 8
        copy1 = self._font_small.render("Configure via companion app", False, DIM2)
        copy2 = self._font_small.render("or set env vars in secrets", False, DIM3)
        surface.blit(copy1, (8, y))
        surface.blit(copy2, (8, y + copy1.get_height() + 4))

        hint = self._font_hint.render("HINT: DBL:BACK", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))
