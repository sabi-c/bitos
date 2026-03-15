from __future__ import annotations

import importlib
import time

import pygame

from device.input.handler import ButtonEvent
from device.screens.base import Screen
from device.ui.fonts import get_font

MENU_ITEMS = [
    ("CHAT", "chat_screen", "ChatScreen"),
    ("CAPTURE", "modals.capture_modal", "CaptureModal"),
    ("TASKS", "tasks_screen", "TasksScreen"),
    ("FOCUS", "focus_screen", "FocusScreen"),
    ("SETTINGS", "settings_screen", "SettingsScreen"),
]


class HomeScreen(Screen):
    SCREEN_NAME = "HOME"

    def on_enter(self):
        self._cursor = 0

    def handle_event(self, event):
        if event == ButtonEvent.SHORT_PRESS:
            self._cursor = (self._cursor + 1) % len(MENU_ITEMS)
            return True
        if event == ButtonEvent.LONG_PRESS:
            _, module, cls = MENU_ITEMS[self._cursor]
            try:
                mod = importlib.import_module(f"device.screens.{module}")
                screen_cls = getattr(mod, cls)
                if self._manager:
                    if cls.endswith("Modal"):
                        self._manager.overlay(screen_cls())
                    else:
                        self._manager.push(screen_cls())
            except (ImportError, AttributeError):
                return True
            return True
        return super().handle_event(event)

    def get_hint(self):
        return "[tap] scroll  [hold] enter  [2x] lock"

    def draw(self, surface):
        w, _ = surface.get_size()
        surface.fill((0, 0, 0))

        col_w = w // 3
        now = time.localtime()
        widgets = [
            ("TIME", f"{(now.tm_hour % 12) or 12}:{now.tm_min:02d}"),
            ("WEATHER", "72°F"),
            ("TASKS", "4"),
        ]
        for i, (lbl, val) in enumerate(widgets):
            rect = pygame.Rect(i * col_w, 0, col_w, 54)
            pygame.draw.rect(surface, (51, 51, 51), rect, 2)
            l = get_font(4).render(lbl, False, (51, 51, 51))
            v = get_font(12).render(val, False, (255, 255, 255))
            surface.blit(l, (rect.x + 5, rect.y + 6))
            surface.blit(v, (rect.x + 5, rect.y + 18))

        item_h = 36
        menu_top = 54
        font_item = get_font(8)
        font_arr = get_font(9)

        for i, (name, _, _) in enumerate(MENU_ITEMS):
            y = menu_top + i * item_h
            rect = pygame.Rect(0, y, w, item_h)
            focused = i == self._cursor
            if focused:
                pygame.draw.rect(surface, (255, 255, 255), rect)
                txt_color = (0, 0, 0)
                arr_color = (0, 0, 0)
            else:
                pygame.draw.line(surface, (17, 17, 17), (0, y + item_h - 1), (w, y + item_h - 1))
                txt_color = (85, 85, 85)
                arr_color = (51, 51, 51)

            item_txt = font_item.render(name, False, txt_color)
            arr_txt = font_arr.render("▶", False, arr_color)
            surface.blit(item_txt, (10, y + (item_h - item_txt.get_height()) // 2))
            surface.blit(arr_txt, (w - arr_txt.get_width() - 10, y + (item_h - arr_txt.get_height()) // 2))
