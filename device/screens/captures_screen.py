from __future__ import annotations

import pygame

from device.screens.base import Screen
from device.screens.nav import NavigationEvent
from device.screens.registry import register_app
from device.ui.fonts import get_font


@register_app
class CapturesScreen(Screen):
    SCREEN_NAME = "CAPTURES"
    MENU_ICON = "CAP"
    MENU_ORDER = 80

    def on_enter(self):
        self._cursor = 0
        self._items = ["Shot log note", "Voice memo", "QR snapshot"]

    def handle_nav(self, event: str) -> bool:
        if event == NavigationEvent.NEXT:
            self._cursor = (self._cursor + 1) % len(self._items)
            return True
        if event == NavigationEvent.SELECT:
            return True
        return super().handle_nav(event)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((0, 0, 0))
        surface.blit(get_font(5).render("CAPTURE HISTORY", False, (51, 51, 51)), (8, 6))
        y = 20
        for i, item in enumerate(self._items):
            focus = i == self._cursor
            if focus:
                pygame.draw.rect(surface, (255, 255, 255), (0, y - 2, 240, 24))
            fg = (0, 0, 0) if focus else (85, 85, 85)
            surface.blit(get_font(6).render(item, False, fg), (8, y + 4))
            y += 28
