"""BITOS Home panel placeholder used for Phase 2 shell bootstrapping."""
import pygame

from screens.base import BaseScreen
from display.tokens import BLACK, WHITE, DIM2, DIM3, HAIRLINE, PHYSICAL_W, PHYSICAL_H, FONT_PATH, FONT_SIZES


class HomePanel(BaseScreen):
    """Minimal home panel with route to chat."""

    def __init__(self, on_open_chat=None):
        self._on_open_chat = on_open_chat
        try:
            self._font_title = pygame.font.Font(FONT_PATH, FONT_SIZES["title"])
            self._font_body = pygame.font.Font(FONT_PATH, FONT_SIZES["body"])
            self._font_small = pygame.font.Font(FONT_PATH, FONT_SIZES["small"])
        except FileNotFoundError:
            self._font_title = pygame.font.SysFont("monospace", FONT_SIZES["title"])
            self._font_body = pygame.font.SysFont("monospace", FONT_SIZES["body"])
            self._font_small = pygame.font.SysFont("monospace", FONT_SIZES["small"])

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
