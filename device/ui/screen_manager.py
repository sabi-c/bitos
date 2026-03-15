"""
BITOS Screen Manager
Manages screen stack. Draws status bar + hint bar over all screens.
"""
from __future__ import annotations

import time

import pygame

from device.input.handler import ButtonEvent
from device.ui.draw_utils import draw_battery, draw_wifi
from device.ui.fonts import get_font

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
DIM = (51, 51, 51)
MID = (85, 85, 85)

STATUS_H = 20
HINT_H = 20
SCREEN_W = 240
SCREEN_H = 280
CONTENT_H = SCREEN_H - STATUS_H - HINT_H


class ScreenManager:
    def __init__(self, surface: pygame.Surface):
        self._surface = surface
        self._stack: list = []
        self._modal = None
        self._font_tiny = get_font(5)
        self._font_sm = get_font(6)

    def push(self, screen) -> None:
        if self._stack:
            self._stack[-1].on_pause()
        screen._manager = self
        self._stack.append(screen)
        screen.on_enter()

    def pop(self) -> None:
        if len(self._stack) <= 1:
            return
        screen = self._stack.pop()
        screen.on_exit()
        if self._stack:
            self._stack[-1].on_resume()

    def replace(self, screen) -> None:
        if self._stack:
            old = self._stack.pop()
            old.on_exit()
        screen._manager = self
        self._stack.append(screen)
        screen.on_enter()

    def overlay(self, modal) -> None:
        modal._manager = self
        self._modal = modal
        modal.on_enter()

    def dismiss_overlay(self) -> None:
        if self._modal:
            self._modal.on_exit()
            self._modal = None

    def clear_to(self, screen_class) -> None:
        while len(self._stack) > 1:
            self._stack.pop().on_exit()
        self.replace(screen_class())

    def current_screen_name(self) -> str:
        if self._stack:
            return self._stack[-1].SCREEN_NAME
        return "?"

    def handle_event(self, event: ButtonEvent) -> None:
        if event == ButtonEvent.TRIPLE_PRESS:
            from device.screens.modals.capture_modal import CaptureModal

            self.overlay(CaptureModal())
            return
        if event == ButtonEvent.POWER_GESTURE:
            from device.screens.modals.power_menu import PowerMenuModal

            self.overlay(PowerMenuModal())
            return
        if self._modal:
            self._modal.handle_event(event)
            return
        if self._stack:
            self._stack[-1].handle_event(event)

    def draw(self) -> None:
        self._surface.fill(BLACK)

        content_surf = pygame.Surface((SCREEN_W, CONTENT_H))
        content_surf.fill(BLACK)
        if self._stack:
            active = self._stack[-1]
            active.draw(content_surf)
            active.update(1 / 15)
        self._surface.blit(content_surf, (0, STATUS_H))

        if self._modal:
            modal_surf = pygame.Surface((SCREEN_W, CONTENT_H))
            modal_surf.fill(BLACK)
            self._modal.draw(modal_surf)
            self._surface.blit(modal_surf, (0, STATUS_H))

        self._draw_status_bar()

        hint = ""
        if self._modal:
            hint = self._modal.get_hint()
        elif self._stack:
            hint = self._stack[-1].get_hint()
        self._draw_hint_bar(hint)

    def _draw_status_bar(self) -> None:
        bar = pygame.Rect(0, 0, SCREEN_W, STATUS_H)
        pygame.draw.rect(self._surface, WHITE, bar)

        now = time.localtime()
        h, m = now.tm_hour % 12 or 12, now.tm_min
        time_str = f"{h}:{m:02d}"
        txt = self._font_sm.render(time_str, False, BLACK)
        self._surface.blit(txt, (6, (STATUS_H - txt.get_height()) // 2))

        name = self.current_screen_name()
        ntxt = self._font_tiny.render(name, False, (80, 80, 80))
        self._surface.blit(ntxt, (SCREEN_W // 2 - ntxt.get_width() // 2, (STATUS_H - ntxt.get_height()) // 2))

        draw_wifi(self._surface, 190, 4, 14, 12, BLACK)
        draw_battery(self._surface, 208, 4, 18, 12, BLACK)

    def _draw_hint_bar(self, hint: str) -> None:
        bar = pygame.Rect(0, SCREEN_H - HINT_H, SCREEN_W, HINT_H)
        pygame.draw.rect(self._surface, (10, 10, 10), bar)
        pygame.draw.line(self._surface, DIM, (0, SCREEN_H - HINT_H), (SCREEN_W, SCREEN_H - HINT_H))
        txt = self._font_tiny.render(hint, False, MID)
        self._surface.blit(txt, (SCREEN_W // 2 - txt.get_width() // 2, SCREEN_H - HINT_H + (HINT_H - txt.get_height()) // 2))
