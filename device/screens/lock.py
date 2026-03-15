"""BITOS Lock screen (Phase 2 milestone starter)."""
import time
import logging
import pygame

from screens.base import BaseScreen
from display.tokens import BLACK, WHITE, DIM3, HAIRLINE, PHYSICAL_W, PHYSICAL_H
from display.theme import merge_runtime_ui_settings, load_ui_font


class LockScreen(BaseScreen):
    """Simple lock gate before entering home flow."""

    _owns_status_bar: bool = True

    def __init__(self, on_home=None, ui_settings: dict | None = None):
        self._on_home = on_home
        self._is_unlocking = False
        self._ui_settings = merge_runtime_ui_settings(ui_settings)

        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)

        logging.getLogger(__name__).info(
            "lock_font_size title=%s",
            self._font_title.get_height(),
        )

    def handle_action(self, action: str):
        if action in {"SHORT_PRESS", "LONG_PRESS", "DOUBLE_PRESS"}:
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
        device_name = self._font_body.render("BITOS", False, DIM3)
        hint = self._font_small.render("PRESS TO UNLOCK", False, WHITE)

        block_h = clock.get_height() + 8 + device_name.get_height() + 12 + 1 + 12 + hint.get_height()
        start_y = max(30, (PHYSICAL_H - block_h) // 2)

        clock_x = (PHYSICAL_W - clock.get_width()) // 2
        surface.blit(clock, (clock_x, start_y))

        name_y = start_y + clock.get_height() + 8
        name_x = (PHYSICAL_W - device_name.get_width()) // 2
        surface.blit(device_name, (name_x, name_y))

        line_y = name_y + device_name.get_height() + 12
        pygame.draw.line(surface, HAIRLINE, (30, line_y), (PHYSICAL_W - 30, line_y))

        hint_y = line_y + 12
        hint_x = (PHYSICAL_W - hint.get_width()) // 2
        surface.blit(hint, (hint_x, hint_y))

    def _unlock(self):
        if self._is_unlocking:
            return
        self._is_unlocking = True
        if self._on_home:
            self._on_home()
