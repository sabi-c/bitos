from __future__ import annotations

import time

import pygame

from device.input.handler import ButtonEvent
from device.screens.base import Screen
from device.ui.fonts import get_font

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
DIM = (51, 51, 51)
MID = (85, 85, 85)


class ChatScreen(Screen):
    SCREEN_NAME = "CHAT"

    def on_enter(self):
        self._quick_idx = 0
        self._streaming = True
        self._messages = [
            ("ai", "Need me to prep call notes?"),
            ("me", "Yes — for 3pm client sync."),
            ("ai", "Done. Added agenda + risks."),
        ]
        self._quick = ["Summarize", "Draft reply", "Create task", "Follow up"]

    def handle_event(self, event):
        if event == ButtonEvent.SHORT_PRESS:
            self._quick_idx = (self._quick_idx + 1) % len(self._quick)
            return True
        if event == ButtonEvent.LONG_PRESS:
            self._messages.append(("me", self._quick[self._quick_idx]))
            self._streaming = not self._streaming
            return True
        return super().handle_event(event)

    def get_hint(self):
        return "[tap] replies  [hold] send  [2x] back"

    def draw(self, surface: pygame.Surface):
        w, h = surface.get_size()
        surface.fill(BLACK)

        msg_h = 150
        quick_h = 58
        input_h = 32

        y = 6
        for side, text in self._messages[-3:]:
            bubble_w = min(160, 30 + len(text) * 4)
            bubble_h = 28
            is_me = side == "me"
            bx = w - bubble_w - 22 if is_me else 22
            avx = w - 18 if is_me else 6

            pygame.draw.rect(surface, WHITE, (avx, y + 5, 14, 14), 1)
            surface.blit(get_font(6).render("U" if is_me else "A", False, WHITE), (avx + 3, y + 10))

            if is_me:
                pygame.draw.rect(surface, WHITE, (bx, y, bubble_w, bubble_h))
                tcol = BLACK
            else:
                pygame.draw.rect(surface, WHITE, (bx, y, bubble_w, bubble_h), 2)
                tcol = WHITE
            surface.blit(get_font(6).render(text[:32], False, tcol), (bx + 6, y + 10))
            y += bubble_h + 8

        if self._streaming and y < msg_h:
            dots = "." * (int(time.time() * 3) % 3 + 1)
            surface.blit(get_font(7).render(dots, False, MID), (24, y + 4))

        qy = msg_h
        pygame.draw.line(surface, WHITE, (0, qy), (w, qy), 2)
        chip_x = 6
        chip_y = qy + 8
        for i, label in enumerate(self._quick):
            chip_w = get_font(6).render(label, False, WHITE).get_width() + 10
            if chip_x + chip_w >= w - 6:
                chip_x = 6
                chip_y += 18
            col = WHITE if i == self._quick_idx else (42, 42, 42)
            pygame.draw.rect(surface, col, (chip_x, chip_y, chip_w, 14), 2)
            tcol = WHITE if i == self._quick_idx else DIM
            surface.blit(get_font(6).render(label, False, tcol), (chip_x + 5, chip_y + 4))
            chip_x += chip_w + 5

        iy = h - input_h
        pygame.draw.line(surface, WHITE, (0, iy), (w, iy), 3)
        pygame.draw.line(surface, WHITE, (w - 32, iy), (w - 32, h), 3)
        surface.blit(get_font(5).render("TYPE A REPLY...", False, DIM), (7, iy + 11))
        surface.blit(get_font(8).render(">", False, WHITE), (w - 20, iy + 11))
