"""Ambient clock screen — shown during idle instead of full display-off.

Displays a minimal clock face with time, date, and optional battery info
at very dim backlight (30%). Any button press wakes the device and returns
to the previous screen.
"""

import time
import logging

import pygame

from screens.base import BaseScreen
from display.tokens import BLACK, WHITE, DIM3, PHYSICAL_W, PHYSICAL_H
from display.theme import merge_runtime_ui_settings, load_ui_font
from power.battery import BatteryMonitor

logger = logging.getLogger(__name__)


class AmbientClockScreen(BaseScreen):
    """Minimal clock face for idle ambient display."""

    SCREEN_NAME: str = "AMBIENT_CLOCK"
    _owns_status_bar: bool = True  # We render our own minimal layout

    def __init__(self, ui_settings: dict | None = None):
        super().__init__()
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_clock = load_ui_font("time_large", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)

        self._clock_text = ""
        self._date_text = ""
        self._last_clock_update = 0.0

    def update(self, dt: float):
        now = time.time()
        if now - self._last_clock_update >= 1.0:
            t = time.localtime()
            self._clock_text = f"{t.tm_hour:02d}:{t.tm_min:02d}"
            days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
            months = [
                "JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                "JUL", "AUG", "SEP", "OCT", "NOV", "DEC",
            ]
            self._date_text = f"{days[t.tm_wday]} {months[t.tm_mon - 1]} {t.tm_mday}"
            self._last_clock_update = now

    def handle_action(self, action: str):
        """Any button press should wake — handled by IdleManager, not here."""
        pass

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # Large centered time
        clock_surf = self._font_clock.render(
            self._clock_text or "00:00", False, WHITE,
        )
        clock_x = (PHYSICAL_W - clock_surf.get_width()) // 2
        clock_y = (PHYSICAL_H // 2) - clock_surf.get_height()
        surface.blit(clock_surf, (clock_x, clock_y))

        # Date below
        date_surf = self._font_small.render(
            self._date_text or "", False, DIM3,
        )
        date_x = (PHYSICAL_W - date_surf.get_width()) // 2
        date_y = clock_y + clock_surf.get_height() + 8
        surface.blit(date_surf, (date_x, date_y))

        # Battery in bottom-right corner
        try:
            batt = BatteryMonitor().get_status()
            pct = batt.get("pct", 0)
            charging = batt.get("charging", False)
            icon = "\u26a1" if charging else ""
            batt_text = f"{icon}{pct}%" if icon else f"{pct}%"
            batt_surf = self._font_small.render(batt_text, False, DIM3)
            batt_x = PHYSICAL_W - batt_surf.get_width() - 8
            batt_y = PHYSICAL_H - batt_surf.get_height() - 6
            surface.blit(batt_surf, (batt_x, batt_y))
        except Exception:
            pass

    def draw(self, surface: pygame.Surface) -> None:
        """Alias for render — Screen base class calls draw()."""
        self.render(surface)
