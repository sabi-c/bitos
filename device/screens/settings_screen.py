from __future__ import annotations

import pygame

from device.screens.base import Screen
from device.screens.nav import NavigationEvent
from device.screens.registry import register_app
from device.ui.draw_utils import draw_ai, draw_settings, draw_signal, draw_wifi
from device.ui.fonts import get_font

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
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


@register_app
class SettingsScreen(Screen):
    SCREEN_NAME = "SETTINGS"
    MENU_ICON = "SET"
    MENU_ORDER = 40

    def on_enter(self):
        self._cursor = 1

    def handle_nav(self, event: str) -> bool:
        actionable = [i for i, row in enumerate(ROWS) if row[0] != "section"]
        idx = actionable.index(self._cursor)
        if event == NavigationEvent.NEXT:
            self._cursor = actionable[(idx + 1) % len(actionable)]
            return True
        if event == NavigationEvent.SELECT:
            t, label, value, _ = ROWS[self._cursor]
            if t == "toggle":
                ROWS[self._cursor] = (t, label, "OFF" if value == "ON" else "ON", "signal")
            return True
        return super().handle_nav(event)

    def draw(self, surface: pygame.Surface):
        surface.fill(BLACK)
        avatar = pygame.Rect(8, 8, 32, 32)
        pygame.draw.rect(surface, WHITE, avatar, 2)
        surface.blit(get_font(7).render("SC", False, WHITE), (avatar.x + 5, avatar.y + 11))
        surface.blit(get_font(7).render("SEB CONTRERAS", False, WHITE), (48, 12))
        surface.blit(get_font(5).render("FREELANCE OPS · LA", False, (68, 68, 68)), (48, 26))
        pygame.draw.line(surface, (17, 17, 17), (0, 47), (240, 47), 2)
        y = 48
        for i, (rtype, label, value, icon) in enumerate(ROWS):
            if rtype == "section":
                pygame.draw.rect(surface, (5, 5, 5), (0, y, 240, 14))
                surface.blit(get_font(5).render(label, False, (51, 51, 51)), (8, y + 4))
                y += 14
                continue
            focused = i == self._cursor
            if focused:
                pygame.draw.rect(surface, WHITE, (0, y, 240, 24))
                fg, sub = BLACK, (34, 34, 34)
            else:
                fg, sub = WHITE, MID
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
                pygame.draw.rect(surface, fg, (126, y + 10, 72, 6), 1)
                pygame.draw.rect(surface, fg if focused else WHITE, (127, y + 11, 49, 4))
                surface.blit(get_font(5).render(value, False, sub), (206, y + 9))
            else:
                if value:
                    vtxt = get_font(5).render(value, False, sub)
                    surface.blit(vtxt, (240 - vtxt.get_width() - 18, y + 9))
                if rtype in {"arrow", "toggle"}:
                    surface.blit(get_font(6).render("▶", False, sub), (222, y + 8))
            y += 24
