from __future__ import annotations

from datetime import datetime

import pygame

from device.input.handler import ButtonEvent
from device.ui.draw_utils import draw_battery, draw_wifi
from device.ui.fonts import get_font

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY_11 = (17, 17, 17)
GRAY_51 = (51, 51, 51)
GRAY_85 = (85, 85, 85)


class ScreenManager:
    def __init__(self, surface: pygame.Surface):
        self._surface = surface
        self._stack = []
        self._overlay = None

    def _bind(self, screen):
        screen._manager = self
        return screen

    def push(self, screen):
        if self._stack:
            self._stack[-1].on_pause()
        screen = self._bind(screen)
        self._stack.append(screen)
        screen.on_enter()

    def pop(self):
        if not self._stack:
            return None
        top = self._stack.pop()
        top.on_exit()
        if self._stack:
            self._stack[-1].on_resume()
        return top

    def replace(self, screen):
        self.pop()
        self.push(screen)

    def overlay(self, modal):
        self._overlay = self._bind(modal)
        self._overlay.on_enter()

    def dismiss_overlay(self):
        if self._overlay is not None:
            self._overlay.on_exit()
            self._overlay = None

    def _top(self):
        return self._overlay if self._overlay is not None else (self._stack[-1] if self._stack else None)

    def handle_event(self, event):
        if event == ButtonEvent.TRIPLE_PRESS:
            try:
                from device.overlays.capture import CaptureModal

                self.overlay(CaptureModal())
                return True
            except Exception:
                return False
        if event == ButtonEvent.POWER_GESTURE:
            try:
                from device.overlays.power_menu import PowerMenuModal

                self.overlay(PowerMenuModal())
                return True
            except Exception:
                return False

        target = self._top()
        if target is None:
            return False
        return bool(target.handle_event(event))

    def draw(self):
        self._surface.fill(BLACK)

        content = pygame.Surface((240, 240))
        content.fill(BLACK)
        top = self._top()
        if top is not None:
            top.draw(content)
        self._surface.blit(content, (0, 20))

        pygame.draw.rect(self._surface, WHITE, (0, 0, 240, 20))
        time_text = get_font(7).render(datetime.now().strftime("%I:%M").lstrip("0"), False, BLACK)
        self._surface.blit(time_text, (4, 6))

        name = top.get_breadcrumb() if top else ""
        name_text = get_font(5).render(name, False, GRAY_85)
        self._surface.blit(name_text, (120 - name_text.get_width() // 2, 7))

        draw_wifi(self._surface, 204, 5, 12, 10, BLACK)
        draw_battery(self._surface, 220, 5, 14, 10, BLACK)

        pygame.draw.rect(self._surface, GRAY_11, (0, 260, 240, 20))
        hint = top.get_hint() if top else ""
        hint_text = get_font(5).render(hint, False, GRAY_85)
        self._surface.blit(hint_text, (120 - hint_text.get_width() // 2, 267))
