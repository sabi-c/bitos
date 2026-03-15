"""BITOS Home Screen (Hub)."""

import time

import pygame

from device.screens.base import Screen
from device.screens.nav import NavigationEvent
from device.screens.registry import APP_REGISTRY
from device.ui.fonts import get_font

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
DIM = (17, 17, 17)
MID = (85, 85, 85)
DARK_BORDER = (51, 51, 51)
WIDGET_H = 52
ITEM_H = 37


class HomeScreen(Screen):
    SCREEN_NAME = "HOME"
    MENU_ICON = "⌂"

    def on_enter(self):
        self._cursor = 0
        self._apps = sorted(APP_REGISTRY, key=lambda cls: getattr(cls, "MENU_ORDER", 99))

    def on_resume(self):
        self._apps = sorted(APP_REGISTRY, key=lambda cls: getattr(cls, "MENU_ORDER", 99))

    def handle_nav(self, event: str) -> bool:
        if event == NavigationEvent.NEXT:
            self._cursor = (self._cursor + 1) % len(self._apps) if self._apps else 0
            return True
        if event == NavigationEvent.SELECT and self._apps:
            if self._manager:
                self._manager.push(self._apps[self._cursor]())
            return True
        if event == NavigationEvent.BACK:
            if self._manager:
                self._manager.pop()
            return True
        return False

    def get_hint(self) -> str:
        return "[tap] scroll  [hold] enter  [2x] lock"

    def draw(self, surf: pygame.Surface) -> None:
        w, _ = 240, 240
        surf.fill(BLACK)
        now = time.localtime()
        h12 = now.tm_hour % 12 or 12
        widgets = [("TIME", f"{h12}:{now.tm_min:02d}"), ("WEATHER", "72°F"), ("TASKS", "4")]
        col_w = w // 3
        for i, (lbl, val) in enumerate(widgets):
            r = pygame.Rect(i * col_w, 0, col_w, WIDGET_H)
            pygame.draw.rect(surf, DARK_BORDER, r, 2)
            surf.blit(get_font(4).render(lbl, False, DARK_BORDER), (r.x + 5, r.y + 5))
            surf.blit(get_font(11).render(val, False, WHITE), (r.x + 5, r.y + 18))

        menu_y = WIDGET_H + 2
        for i, cls in enumerate(self._apps):
            y = menu_y + i * ITEM_H
            focused = i == self._cursor
            r = pygame.Rect(0, y, w, ITEM_H)
            if focused:
                pygame.draw.rect(surf, WHITE, r)
                tc, ac = BLACK, BLACK
            else:
                pygame.draw.line(surf, DIM, (0, y + ITEM_H - 1), (w, y + ITEM_H - 1))
                tc, ac = MID, DARK_BORDER
            name = getattr(cls, "SCREEN_NAME", cls.__name__)
            item_txt = get_font(8).render(name, False, tc)
            arr_txt = get_font(9).render("▶", False, ac)
            surf.blit(item_txt, (10, y + (ITEM_H - item_txt.get_height()) // 2))
            surf.blit(arr_txt, (w - arr_txt.get_width() - 10, y + (ITEM_H - arr_txt.get_height()) // 2))
