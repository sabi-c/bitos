from __future__ import annotations

from datetime import datetime

import pygame

from device.input.handler import ButtonEvent
from device.screens.base import Screen
from device.ui.fonts import get_font

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY_11 = (17, 17, 17)
GRAY_51 = (51, 51, 51)
GRAY_85 = (85, 85, 85)


class PlaceholderScreen(Screen):
    def __init__(self, name: str):
        super().__init__()
        self.SCREEN_NAME = name

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BLACK)
        t = get_font(8).render(self.SCREEN_NAME, False, WHITE)
        surface.blit(t, (120 - t.get_width() // 2, 116))


class HomeScreen(Screen):
    SCREEN_NAME = "HOME"

    def __init__(self):
        super().__init__()
        self._cursor = 0
        self._items = ["CHAT", "CAPTURE", "TASKS", "FOCUS", "SETTINGS"]

    def handle_event(self, event: ButtonEvent) -> bool:
        if event == ButtonEvent.SHORT_PRESS:
            self._cursor = (self._cursor + 1) % len(self._items)
            return True
        if event == ButtonEvent.LONG_PRESS:
            if self._manager:
                self._manager.push(PlaceholderScreen(self._items[self._cursor]))
            return True
        if event == ButtonEvent.DOUBLE_PRESS:
            if self._manager:
                self._manager.pop()
            return True
        return False

    def get_hint(self) -> str:
        return "[tap] scroll  [hold] enter  [2x] lock"

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill(BLACK)

        strip_y = 0
        col_w = 80
        labels = ["TIME", "WEATHER", "TASKS"]
        values = [datetime.now().strftime("%I:%M").lstrip("0"), "72°F", "4"]
        for i in range(3):
            x = i * col_w
            pygame.draw.rect(surface, GRAY_51, (x, strip_y, col_w, 54), 2)
            l = get_font(5).render(labels[i], False, GRAY_85)
            v = get_font(7).render(values[i], False, WHITE)
            surface.blit(l, (x + (col_w - l.get_width()) // 2, 10))
            surface.blit(v, (x + (col_w - v.get_width()) // 2, 28))

        row_h = 37
        start_y = 54
        for idx, item in enumerate(self._items):
            y = start_y + idx * row_h
            pygame.draw.line(surface, GRAY_11, (0, y + row_h - 1), (240, y + row_h - 1), 1)
            focused = idx == self._cursor
            if focused:
                pygame.draw.rect(surface, WHITE, (0, y, 240, row_h))
                text_color = BLACK
                arrow_color = BLACK
            else:
                text_color = GRAY_85
                arrow_color = GRAY_51
            text = get_font(8).render(item, False, text_color)
            surface.blit(text, (16, y + 13))
            arrow = get_font(8).render("▶", False, arrow_color)
            surface.blit(arrow, (220 - arrow.get_width(), y + 13))
