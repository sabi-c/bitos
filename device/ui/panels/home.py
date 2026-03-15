"""Home panel — time, date, weather, next tasks.

Renders into 156x280 right-panel surface.
Matches bitos-nav-v2.html .home-panel specification.
"""

from datetime import datetime

import pygame

from device.ui.fonts import get_font
from device.ui.font_sizes import TIME_LARGE, TITLE, BODY, CAPTION
from device.ui.panels.base import (
    BasePanel, PANEL_W, BLACK, WHITE, GRAY_555, GRAY_444, GRAY_333,
    GRAY_AAA, GRAY_1A, SEP_COLOR,
)


class HomePanel(BasePanel):
    TITLE = "HOME"

    def __init__(self):
        self.weather_temp = "72"
        self.weather_desc = "PARTLY CLOUDY"
        self.weather_location = "BURBANK CA"
        self.weather_hi = "76"
        self.weather_lo = "61"
        self.tasks = [
            {"text": "INVOICE JOAQUIN", "urgent": True, "focused": True},
            {"text": "TICKET FORMATTER", "urgent": False, "focused": False},
            {"text": "EL CAMINO BRAKES", "urgent": False, "focused": False},
        ]
        self.focused_task = 0

    def render(self, surface: pygame.Surface) -> None:
        surface.fill(BLACK)

        now = datetime.now()

        # Header with time on right
        right_time = now.strftime("%I:%M").lstrip("0")
        y = self.draw_header(surface, right_text=right_time, right_color=GRAY_555)

        # Large time display
        font_22 = get_font(TIME_LARGE)
        h = now.hour % 12 or 12
        m = now.strftime("%M")
        time_text = f"{h}:{m}"
        time_surf = font_22.render(time_text, False, WHITE)
        time_x = (PANEL_W - time_surf.get_width()) // 2
        surface.blit(time_surf, (time_x, y + 12))
        y += 12 + time_surf.get_height() + 4

        # Date
        # weekday(): Mon=0..Sun=6; we want Sun=0..Sat=6
        days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
        months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                  "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
        date_str = f"{days[now.weekday()]} {months[now.month - 1]} {now.day}"
        font_date = get_font(CAPTION)
        date_surf = font_date.render(date_str, False, GRAY_555)
        surface.blit(date_surf, ((PANEL_W - date_surf.get_width()) // 2, y))
        y += date_surf.get_height() + 10

        # Weather box (bordered)
        wx = 8
        ww = PANEL_W - 16
        wh = 40
        pygame.draw.rect(surface, GRAY_1A, (wx, y, ww, wh), 2)

        # Temp
        font_14 = get_font(TITLE)
        temp_surf = font_14.render(f"{self.weather_temp}\xb0", False, WHITE)
        surface.blit(temp_surf, (wx + 8, y + (wh - temp_surf.get_height()) // 2))

        # Weather info (right side of box)
        font_5 = get_font(CAPTION)
        info_x = wx + 8 + temp_surf.get_width() + 6
        info_lines = [self.weather_desc, self.weather_location,
                      f"H:{self.weather_hi} L:{self.weather_lo}"]
        iy = y + 6
        for line in info_lines:
            info_surf = font_5.render(line, False, GRAY_444)
            surface.blit(info_surf, (info_x, iy))
            iy += int(font_5.get_height() * 1.8)

        y += wh + 10

        # "NEXT TASK" section header
        font_section = get_font(CAPTION)
        section_surf = font_section.render("NEXT TASK", False, GRAY_333)
        surface.blit(section_surf, (8, y))
        y += section_surf.get_height() + 4
        pygame.draw.line(surface, SEP_COLOR, (0, y), (PANEL_W, y))
        y += 1

        # Task rows
        font_task = get_font(BODY)
        row_h = 24
        for idx, task in enumerate(self.tasks):
            focused = idx == self.focused_task
            if focused:
                pygame.draw.rect(surface, WHITE, (0, y, PANEL_W, row_h))

            # Dot
            dot_x = 8
            dot_y = y + (row_h - 5) // 2
            dot_color = BLACK if focused else (
                (0xFF, 0x44, 0x44) if task.get("urgent") else GRAY_555
            )
            pygame.draw.rect(surface, dot_color, (dot_x, dot_y, 5, 5))

            # Text
            text_color = BLACK if focused else GRAY_AAA
            text_surf = font_task.render(task["text"], False, text_color)
            surface.blit(text_surf, (dot_x + 5 + 6, y + (row_h - text_surf.get_height()) // 2))

            pygame.draw.line(surface, SEP_COLOR, (0, y + row_h - 1), (PANEL_W, y + row_h - 1))
            y += row_h
