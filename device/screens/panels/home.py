"""BITOS Home panel placeholder used for Phase 2 shell bootstrapping."""
import pygame

from screens.base import BaseScreen
from display.tokens import BLACK, WHITE, DIM2, DIM3, HAIRLINE, PHYSICAL_W, PHYSICAL_H
from display.theme import merge_runtime_ui_settings, load_ui_font


class HomePanel(BaseScreen):
    """Minimal home panel with route to chat."""

    def __init__(self, on_open_chat=None, ui_settings: dict | None = None):
        self._on_open_chat = on_open_chat
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)

    def handle_action(self, action: str):
        if action == "SHORT_PRESS":
            self._open_chat()

    def handle_input(self, event: pygame.event.Event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key in (pygame.K_RETURN, pygame.K_SPACE, pygame.K_c):
            self._open_chat()

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        title = self._font_title.render("HOME", False, WHITE)
        surface.blit(title, (8, 8))
        pygame.draw.line(surface, HAIRLINE, (0, 24), (PHYSICAL_W, 24))

        items = [
            ("CHAT", "READY"),
            ("FOCUS", "SOON"),
            ("TASKS", "SOON"),
            ("SETTINGS", "SOON"),
        ]

        y = 38
        for label, status in items:
            row = self._font_body.render(label, False, WHITE)
            st = self._font_small.render(status, False, DIM2)
            surface.blit(row, (8, y))
            surface.blit(st, (PHYSICAL_W - st.get_width() - 8, y + 2))
            pygame.draw.line(surface, HAIRLINE, (8, y + 12), (PHYSICAL_W - 8, y + 12))
            y += 20

        hint = self._font_small.render("PRESS: OPEN CHAT", False, DIM3)
        surface.blit(hint, (8, PHYSICAL_H - 14))

    def _open_chat(self):
        if self._on_open_chat:
            self._on_open_chat()
