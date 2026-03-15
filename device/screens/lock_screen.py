"""BITOS Lock Screen."""

import time

import pygame

from device.screens.base import Screen
from device.screens.nav import NavigationEvent
from device.ui.fonts import get_font

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
DIM = (34, 34, 34)
MID = (85, 85, 85)
DAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


class LockScreen(Screen):
    SCREEN_NAME = "BITOS"
    MENU_ICON = "LCK"

    def handle_nav(self, event: str) -> bool:
        if event == NavigationEvent.SELECT:
            from device.screens.home_screen import HomeScreen

            if self._manager:
                self._manager.push(HomeScreen())
            return True
        if event == NavigationEvent.NEXT:
            return True
        return False

    def get_hint(self) -> str:
        return "[hold] unlock"

    def draw(self, surf: pygame.Surface) -> None:
        w, h = 240, 240
        surf.fill(BLACK)
        now = time.localtime()

        h12 = now.tm_hour % 12 or 12
        clock_str = f"{h12}:{now.tm_min:02d}"
        clock_txt = get_font(40).render(clock_str, False, WHITE)
        cx = w // 2 - clock_txt.get_width() // 2
        cy = int(h * 0.22)
        surf.blit(clock_txt, (cx, cy))

        date_str = f"{DAYS[now.tm_wday]}  {MONTHS[now.tm_mon - 1]} {now.tm_mday}"
        date_txt = get_font(7).render(date_str, False, MID)
        surf.blit(date_txt, (w // 2 - date_txt.get_width() // 2, cy + clock_txt.get_height() + 8))

        notifs = ["JOAQUIN: Can you call re: OT rate", "OVATION: Your itinerary LAX→JFK"]
        ny = int(h * 0.58)
        font_sm = get_font(6)
        for txt in notifs:
            pygame.draw.rect(surf, DIM, (8, ny, w - 16, 22), 2)
            rendered = font_sm.render(txt, False, MID)
            while rendered.get_width() > (w - 36) and len(txt) > 3:
                txt = txt[:-1]
                rendered = font_sm.render(txt + "…", False, MID)
            surf.blit(rendered, (14, ny + (22 - rendered.get_height()) // 2))
            ny += 26

        uh_y = ny + 10
        pygame.draw.line(surf, DIM, (0, uh_y), (w, uh_y))
        htxt = get_font(6).render("○  HOLD TO UNLOCK  ○", False, (51, 51, 51))
        surf.blit(htxt, (w // 2 - htxt.get_width() // 2, uh_y + 8))
