from __future__ import annotations

import time

import pygame

from device.input.handler import ButtonEvent
from device.screens.base import Screen
from device.ui.draw_utils import draw_lock, draw_mail
from device.ui.fonts import get_font

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
DIM = (34, 34, 34)
MID = (85, 85, 85)
DIM2 = (51, 51, 51)


class LockScreen(Screen):
    SCREEN_NAME = "BITOS"

    def on_enter(self):
        self._last_minute = -1
        self._clock_str = "--:--"
        self._dimmed = False

    def handle_event(self, event):
        from device.screens.home_screen import HomeScreen

        if event == ButtonEvent.LONG_PRESS:
            if self._manager:
                self._manager.push(HomeScreen())
            return True
        if event == ButtonEvent.SHORT_PRESS:
            self._dimmed = not self._dimmed
            return True
        return False

    def get_hint(self):
        return "[hold] unlock"

    def get_breadcrumb(self):
        return "BITOS"

    def _update_clock(self) -> time.struct_time:
        now = time.localtime()
        if now.tm_min != self._last_minute:
            self._last_minute = now.tm_min
            h12 = now.tm_hour % 12 or 12
            self._clock_str = f"{h12}:{now.tm_min:02d}"
        return now

    def _truncate(self, text: str, font: pygame.font.Font, max_w: int) -> str:
        if font.render(text, False, MID).get_width() <= max_w:
            return text
        base = text
        while base and font.render(base + "...", False, MID).get_width() > max_w:
            base = base[:-1]
        return (base + "...") if base else "..."

    def draw(self, surface: pygame.Surface):
        w, h = surface.get_size()
        surface.fill(BLACK)

        now = self._update_clock()

        font_big = get_font(40)
        clock_txt = font_big.render(self._clock_str, False, MID if self._dimmed else WHITE)
        cx = w // 2 - clock_txt.get_width() // 2
        cy = int(h * 0.24) - clock_txt.get_height() // 2
        surface.blit(clock_txt, (cx, cy))

        days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        date_str = f"{days[now.tm_wday]} {months[now.tm_mon - 1]} {now.tm_mday:02d} · {1900 + now.tm_year - 1900}"
        font_date = get_font(7)
        date_txt = font_date.render(date_str, False, MID)
        surface.blit(date_txt, (w // 2 - date_txt.get_width() // 2, cy + clock_txt.get_height() + 8))

        notifs = [
            "JOAQUIN: Can you call me re: OT rate",
            "OVATION: Your itinerary LAX→JFK",
        ]
        notif_y = int(h * 0.56)
        row_h = 24
        font_sm = get_font(6)

        draw_lock(surface, 12, notif_y + 5, 12, 12, MID)
        for text in notifs:
            rect = pygame.Rect(8, notif_y, w - 16, row_h)
            pygame.draw.rect(surface, DIM, rect, 2)
            draw_mail(surface, rect.x + 6, rect.y + 6, 12, 10, MID)
            t = self._truncate(text, font_sm, w - 40)
            rendered = font_sm.render(t, False, MID)
            surface.blit(rendered, (rect.x + 24, rect.y + (row_h - rendered.get_height()) // 2))
            notif_y += row_h + 4

        uh_y = notif_y + 8
        pygame.draw.line(surface, DIM, (0, uh_y), (w, uh_y))
        font_hint = get_font(6)
        hint = font_hint.render("○  HOLD TO UNLOCK  ○", False, DIM2)
        surface.blit(hint, (w // 2 - hint.get_width() // 2, uh_y + 8))
