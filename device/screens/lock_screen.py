from __future__ import annotations

from datetime import datetime

import pygame

from device.input.handler import ButtonEvent
from device.screens.base import Screen
from device.screens.home_screen import HomeScreen
from device.ui.draw_utils import draw_mail
from device.ui.fonts import get_font

WHITE = (255, 255, 255)
GRAY_33 = (51, 51, 51)
GRAY_85 = (85, 85, 85)


class LockScreen(Screen):
    SCREEN_NAME = "LOCK"

    def handle_event(self, event: ButtonEvent) -> bool:
        if event == ButtonEvent.SHORT_PRESS:
            return True
        if event == ButtonEvent.LONG_PRESS:
            if self._manager:
                self._manager.push(HomeScreen())
            return True
        return False

    def get_hint(self) -> str:
        return "[hold] unlock"

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill((0, 0, 0))

        now = datetime.now()
        clock_text = get_font(40).render(now.strftime("%I:%M").lstrip("0"), False, WHITE)
        surface.blit(clock_text, (120 - clock_text.get_width() // 2, 26))

        date_text = get_font(7).render(now.strftime("%a  %b %d").upper(), False, GRAY_85)
        surface.blit(date_text, (120 - date_text.get_width() // 2, 88))

        rows = ["New message from Alex", "Build complete: 4 tasks"]
        y = 140
        for text in rows:
            pygame.draw.rect(surface, GRAY_33, (12, y, 216, 24), 2)
            draw_mail(surface, 18, y + 5, 14, 14, GRAY_85)
            rendered = get_font(6).render(text[:24], False, GRAY_85)
            surface.blit(rendered, (40, y + 8))
            y += 28

        pygame.draw.line(surface, GRAY_33, (0, 224), (240, 224), 1)
        hint = get_font(6).render("○  HOLD TO UNLOCK  ○", False, GRAY_33)
        surface.blit(hint, (120 - hint.get_width() // 2, 230))
