"""BITOS Lock screen (Phase 2 milestone starter)."""
import time
import pygame

from screens.base import BaseScreen
from display.tokens import BLACK, WHITE, DIM3, HAIRLINE, PHYSICAL_W, PHYSICAL_H, FONT_PATH, FONT_SIZES


class LockScreen(BaseScreen):
    """Simple lock gate before entering home flow."""

    def __init__(self, on_unlock=None):
        self._on_unlock = on_unlock
        self._is_unlocking = False

        try:
            self._font_title = pygame.font.Font(FONT_PATH, FONT_SIZES["title"])
            self._font_body = pygame.font.Font(FONT_PATH, FONT_SIZES["body"])
            self._font_small = pygame.font.Font(FONT_PATH, FONT_SIZES["small"])
        except FileNotFoundError:
            self._font_title = pygame.font.SysFont("monospace", FONT_SIZES["title"])
            self._font_body = pygame.font.SysFont("monospace", FONT_SIZES["body"])
            self._font_small = pygame.font.SysFont("monospace", FONT_SIZES["small"])

    def handle_action(self, action: str):
        if action in {"SHORT_PRESS", "LONG_PRESS", "DOUBLE_PRESS", "TRIPLE_PRESS"}:
            self._unlock()

    def handle_input(self, event: pygame.event.Event):
        if event.type != pygame.KEYDOWN:
            return
        # Any key acts as a physical interaction for desktop simulation.
        self._unlock()

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        now = time.localtime()
        clock_text = f"{now.tm_hour:02d}:{now.tm_min:02d}"
        clock = self._font_title.render(clock_text, False, WHITE)
        clock_x = (PHYSICAL_W - clock.get_width()) // 2
        surface.blit(clock, (clock_x, 86))

        device_name = self._font_body.render("BITOS", False, DIM3)
        name_x = (PHYSICAL_W - device_name.get_width()) // 2
        surface.blit(device_name, (name_x, 112))

        pygame.draw.line(surface, HAIRLINE, (30, 146), (PHYSICAL_W - 30, 146))

        hint = self._font_small.render("PRESS TO UNLOCK", False, WHITE)
        hint_x = (PHYSICAL_W - hint.get_width()) // 2
        surface.blit(hint, (hint_x, 160))

    def _unlock(self):
        if self._is_unlocking:
            return
        self._is_unlocking = True
        if self._on_unlock:
            self._on_unlock()
