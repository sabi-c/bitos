from __future__ import annotations

import pygame

from device.screens.base import Screen
from device.screens.nav import NavigationEvent
from device.screens.registry import register_app
from device.ui.fonts import get_font


@register_app
class NotificationsScreen(Screen):
    SCREEN_NAME = "NOTIFS"
    MENU_ICON = "NTF"
    MENU_ORDER = 50

    def on_enter(self):
        self._cursor = 0
        self._items = ["Slack: call moved to 4:30", "Calendar: edit bay hold", "Gmail: revised quote"]

    def handle_nav(self, event: str) -> bool:
        if event == NavigationEvent.NEXT:
            self._cursor = (self._cursor + 1) % len(self._items)
            return True
        return super().handle_nav(event)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((0, 0, 0))
        y = 10
        for i, text in enumerate(self._items):
            focus = i == self._cursor
            if focus:
                pygame.draw.rect(surface, (255, 255, 255), (0, y - 2, 240, 24))
            color = (0, 0, 0) if focus else (85, 85, 85)
            surface.blit(get_font(6).render(text[:32], False, color), (8, y + 5))
            y += 30
