from __future__ import annotations

import pygame

from device.screens.base import Screen
from device.screens.nav import NavigationEvent
from device.screens.registry import register_app
from device.ui.fonts import get_font


@register_app
class MessagesScreen(Screen):
    SCREEN_NAME = "MSGS"
    MENU_ICON = "MSG"
    MENU_ORDER = 60

    def on_enter(self):
        self._cursor = 0
        self._threads = ["Joaquin", "Agent Team", "Studio Ops"]

    def handle_nav(self, event: str) -> bool:
        if event == NavigationEvent.NEXT:
            self._cursor = (self._cursor + 1) % len(self._threads)
            return True
        return super().handle_nav(event)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((0, 0, 0))
        y = 12
        for i, name in enumerate(self._threads):
            focus = i == self._cursor
            if focus:
                pygame.draw.rect(surface, (255, 255, 255), (0, y - 2, 240, 28))
            fg = (0, 0, 0) if focus else (255, 255, 255)
            sub = (34, 34, 34) if focus else (85, 85, 85)
            surface.blit(get_font(7).render(name, False, fg), (8, y + 3))
            surface.blit(get_font(5).render("Tap to cycle", False, sub), (8, y + 14))
            y += 34
