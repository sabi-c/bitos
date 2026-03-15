from __future__ import annotations

import pygame

from device.screens.base import Screen
from device.screens.nav import NavigationEvent
from device.screens.registry import register_app
from device.ui.fonts import get_font


@register_app
class MailScreen(Screen):
    SCREEN_NAME = "MAIL"
    MENU_ICON = "ML"
    MENU_ORDER = 70

    def on_enter(self):
        self._cursor = 0
        self._items = ["Call sheet rev 5", "Budget lock", "Travel hold"]

    def handle_nav(self, event: str) -> bool:
        if event == NavigationEvent.NEXT:
            self._cursor = (self._cursor + 1) % len(self._items)
            return True
        return super().handle_nav(event)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((0, 0, 0))
        y = 10
        for i, subject in enumerate(self._items):
            focus = i == self._cursor
            if focus:
                pygame.draw.rect(surface, (255, 255, 255), (0, y - 2, 240, 24))
            color = (0, 0, 0) if focus else (255, 255, 255)
            surface.blit(get_font(6).render(subject, False, color), (8, y + 4))
            y += 30
