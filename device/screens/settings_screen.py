from __future__ import annotations

import pygame

from device.input.handler import ButtonEvent
from device.screens.base import Screen
from device.ui.draw_utils import draw_ai, draw_settings, draw_signal, draw_wifi
from device.ui.fonts import get_font

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
DIM = (51, 51, 51)
MID = (85, 85, 85)

ROWS = [
    ("section", "CONNECTIVITY", "", ""),
    ("arrow", "WI-FI", "STUDIONET-5G", "wifi"),
    ("toggle", "BLUETOOTH", "ON", "signal"),
    ("section", "DISPLAY", "", ""),
    ("slider", "BRIGHTNESS", "70%", "display"),
    ("section", "AI & AGENT", "", ""),
    ("arrow", "AGENT MODE", "PRODUCER", "ai"),
    ("section", "ABOUT", "", ""),
    ("info", "FIRMWARE", "v1.0.4", "settings"),
]


class SettingsScreen(Screen):
    SCREEN_NAME = "SETTINGS"

    def on_enter(self):
        self._cursor = 1

    def handle_event(self, event):
        actionable = [i for i, row in enumerate(ROWS) if row[0] != "section"]
        idx = actionable.index(self._cursor)
        if event == ButtonEvent.SHORT_PRESS:
            self._cursor = actionable[(idx + 1) % len(actionable)]
            return True
        if event == ButtonEvent.LONG_PRESS:
            t, label, value, _ = ROWS[self._cursor]
            if t == "toggle":
                ROWS[self._cursor] = (t, label, "OFF" if value == "ON" else "ON", "signal")
            return True
        return super().handle_event(event)

    def get_hint(self):
        return "[tap] next  [hold] select  [2x] back"

    def draw(self, surface: pygame.Surface):
        surface.fill(BLACK)
        y = 0

        avatar = pygame.Rect(8, 8, 32, 32)
        pygame.draw.rect(surface, WHITE, avatar, 2)
        surface.blit(get_font(7).render("SC", False, WHITE), (avatar.x + 5, avatar.y + 11))
        surface.blit(get_font(7).render("SEB CONTRERAS", False, WHITE), (48, 12))
        surface.blit(get_font(5).render("FREELANCE OPS · LA", False, (68, 68, 68)), (48, 26))
        pygame.draw.line(surface, (17, 17, 17), (0, 47), (240, 47), 2)
        y = 48

        for i, (rtype, label, value, icon) in enumerate(ROWS):
            if rtype == "section":
                sec = pygame.Rect(0, y, 240, 14)
                pygame.draw.rect(surface, (5, 5, 5), sec)
                surface.blit(get_font(5).render(label, False, (51, 51, 51)), (8, y + 4))
                y += 14
                continue

            rect = pygame.Rect(0, y, 240, 24)
            focused = i == self._cursor
            if focused:
                pygame.draw.rect(surface, WHITE, rect)
                fg = BLACK
                sub = (34, 34, 34)
            else:
                fg = WHITE
                sub = MID
                pygame.draw.line(surface, (17, 17, 17), (0, y + 23), (240, y + 23))

            if icon == "wifi":
                draw_wifi(surface, 8, y + 5, 12, 12, fg)
            elif icon == "signal":
                draw_signal(surface, 8, y + 5, 12, 12, fg)
            elif icon == "ai":
                draw_ai(surface, 8, y + 4, 12, 12, fg)
            else:
                draw_settings(surface, 8, y + 4, 12, 12, fg)

            surface.blit(get_font(6).render(label, False, fg), (26, y + 8))

            if rtype == "slider":
                bx = 126
                by = y + 10
                pygame.draw.rect(surface, fg, (bx, by, 72, 6), 1)
                fill_col = fg if focused else WHITE
                pygame.draw.rect(surface, fill_col, (bx + 1, by + 1, 49, 4))
                surface.blit(get_font(5).render(value, False, sub), (206, y + 9))
            else:
                if value:
                    vtxt = get_font(5).render(value, False, sub)
                    surface.blit(vtxt, (240 - vtxt.get_width() - 18, y + 9))
                if rtype in {"arrow", "toggle"}:
                    arr = get_font(6).render("▶", False, sub)
                    surface.blit(arr, (222, y + 8))
            y += 24
