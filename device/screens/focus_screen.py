from __future__ import annotations

import pygame

from device.screens.base import Screen
from device.screens.nav import NavigationEvent
from device.screens.registry import register_app
from device.ui.fonts import get_font


@register_app
class FocusScreen(Screen):
    SCREEN_NAME = "FOCUS"
    MENU_ICON = "FCS"
    MENU_ORDER = 30

    def on_enter(self):
        self._mode = "WORK"

    def handle_nav(self, event: str) -> bool:
        if event == NavigationEvent.SELECT:
            self._mode = "BREAK" if self._mode == "WORK" else "WORK"
            return True
        return super().handle_nav(event)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((0, 0, 0))
        txt = get_font(20).render(self._mode, False, (255, 255, 255))
        surface.blit(txt, (120 - txt.get_width() // 2, 90))
        hint = get_font(6).render("HOLD TO TOGGLE", False, (85, 85, 85))
        surface.blit(hint, (120 - hint.get_width() // 2, 130))
