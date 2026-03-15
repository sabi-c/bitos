from __future__ import annotations

import pygame

from device.screens.base import Screen
from device.screens.nav import NavigationEvent
from device.screens.registry import register_app
from device.ui.fonts import get_font


@register_app
class TasksScreen(Screen):
    SCREEN_NAME = "TASKS"
    MENU_ICON = "TSK"
    MENU_ORDER = 20

    def on_enter(self):
        self._cursor = 0
        self._tasks = ["Review call notes", "Send producer update", "Prep invoice"]

    def handle_nav(self, event: str) -> bool:
        if event == NavigationEvent.NEXT:
            self._cursor = (self._cursor + 1) % len(self._tasks)
            return True
        if event == NavigationEvent.SELECT:
            self._tasks[self._cursor] = "✓ " + self._tasks[self._cursor].lstrip("✓ ")
            return True
        return super().handle_nav(event)

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((0, 0, 0))
        y = 10
        for i, task in enumerate(self._tasks):
            focus = i == self._cursor
            if focus:
                pygame.draw.rect(surface, (255, 255, 255), (0, y - 2, 240, 24))
            color = (0, 0, 0) if focus else (255, 255, 255)
            surface.blit(get_font(6).render(task, False, color), (8, y + 5))
            y += 30
