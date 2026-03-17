"""HomePreviewPanel — overview with time, greeting, and rotating info ticker.

Top area: large time display + greeting + date + cycling ticker.
Below: quick-access items.
"""

from __future__ import annotations

from datetime import datetime

import pygame

from device.display.theme import get_font
from device.display.tokens import WHITE, DIM2, DIM3, DIM4, HAIRLINE
from device.ui.panels.base import PreviewPanel


TIME_FONT = 22
GREETING_FONT = 9
DATE_FONT = 8
STATUS_FONT = 8
PAD_X = 6
PAD_Y = 6
HEADER_H = 90

TICKER_INTERVAL = 4.0  # seconds between items
TICKER_FADE_DUR = 0.5  # seconds for crossfade

HOME_ITEMS = [
    {"label": "QUICK CHAT", "description": "Start a conversation", "action": "chat"},
    {"label": "TODAY'S TASKS", "description": "View today's tasks", "action": "tasks"},
    {"label": "ACTIVITY", "description": "View notifications", "action": "activity"},
    {"label": "BACK", "description": "Return to sidebar", "action": "back"},
]


def _time_greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    elif hour < 17:
        return "Good afternoon"
    else:
        return "Good evening"


class HomePreviewPanel(PreviewPanel):
    """Preview panel for HOME sidebar item."""

    def __init__(self, on_action: callable):
        super().__init__(items=HOME_ITEMS, on_action=on_action)
        self._next_event: str | None = None
        self._weather: str | None = None
        self._task_count: int | None = None
        self._unread_msgs: int = 0
        self._unread_mail: int = 0
        self._headlines: list[str] = []

        # Ticker state
        self._ticker_items: list[str] = []
        self._ticker_index: int = 0
        self._ticker_timer: float = 0.0
        self._ticker_fade: float = 1.0  # 1.0 = fully visible

    # ── Data setters ──────────────────────────────────────────────

    def set_next_event(self, text: str) -> None:
        """Set next calendar event text, e.g. '10:30a Meeting with John'."""
        self._next_event = text
        self._rebuild_ticker()

    def set_weather(self, text: str) -> None:
        """Set current weather text, e.g. '72F Sunny'."""
        self._weather = text
        self._rebuild_ticker()

    def set_task_count(self, count: int) -> None:
        """Set today's task count."""
        self._task_count = count
        self._rebuild_ticker()

    def set_unread(self, msgs: int, mail: int) -> None:
        """Set unread message and email counts."""
        self._unread_msgs = msgs
        self._unread_mail = mail
        self._rebuild_ticker()

    def set_headlines(self, headlines: list[str]) -> None:
        """Set news/world headlines for the ticker."""
        self._headlines = list(headlines)
        self._rebuild_ticker()

    # ── Ticker helpers ────────────────────────────────────────────

    def _rebuild_ticker(self) -> None:
        """Rebuild the list of ticker strings from available data."""
        items: list[str] = []

        if self._weather:
            items.append(self._weather)

        if self._next_event:
            items.append(self._next_event)

        if self._task_count is not None and self._task_count > 0:
            suffix = "task" if self._task_count == 1 else "tasks"
            items.append(f"{self._task_count} {suffix} today")

        if self._unread_msgs > 0 or self._unread_mail > 0:
            parts: list[str] = []
            if self._unread_msgs > 0:
                parts.append(f"{self._unread_msgs} message{'s' if self._unread_msgs != 1 else ''}")
            if self._unread_mail > 0:
                parts.append(f"{self._unread_mail} email{'s' if self._unread_mail != 1 else ''}")
            items.append(", ".join(parts))

        for h in self._headlines:
            if h:
                items.append(h)

        # Truncate each item to fit the panel pixel width
        status_font = get_font(STATUS_FONT)
        max_width = 156 - PAD_X * 2  # panel width minus padding
        for i, text in enumerate(items):
            if status_font.size(text)[0] > max_width:
                while len(text) > 1 and status_font.size(text + "\u2026")[0] > max_width:
                    text = text[:-1]
                items[i] = text + "\u2026"

        self._ticker_items = items

        # Clamp index if list shrank
        if self._ticker_items:
            self._ticker_index = self._ticker_index % len(self._ticker_items)
        else:
            self._ticker_index = 0

    # ── Update (called each frame) ────────────────────────────────

    def update(self, dt: float) -> None:
        """Advance ticker timer and fade state."""
        if len(self._ticker_items) <= 1:
            self._ticker_fade = 1.0
            return

        self._ticker_timer += dt

        if self._ticker_timer >= TICKER_INTERVAL:
            # Start transition to next item
            self._ticker_timer = 0.0
            self._ticker_index = (self._ticker_index + 1) % len(self._ticker_items)
            self._ticker_fade = 0.0

        # Fade in after switching
        if self._ticker_fade < 1.0:
            self._ticker_fade = min(1.0, self._ticker_fade + dt / TICKER_FADE_DUR)

    # ── Render ────────────────────────────────────────────────────

    def render(self, surface: pygame.Surface) -> None:
        w = surface.get_width()
        time_font = get_font(TIME_FONT)
        greeting_font = get_font(GREETING_FONT)
        date_font = get_font(DATE_FONT)
        status_font = get_font(STATUS_FONT)

        now = datetime.now()

        # ── Large time ──
        y = PAD_Y
        time_str = now.strftime("%I:%M").lstrip("0")
        time_surf = time_font.render(time_str, False, WHITE)
        surface.blit(time_surf, (PAD_X, y))
        y += time_font.get_height() + 2

        # ── Greeting ──
        greet = _time_greeting()
        greet_surf = greeting_font.render(greet, False, DIM2)
        surface.blit(greet_surf, (PAD_X, y))
        y += greeting_font.get_height() + 2

        # ── Date ──
        date_str = now.strftime("%A, %b %d")
        date_surf = date_font.render(date_str, False, DIM3)
        surface.blit(date_surf, (PAD_X, y))
        y += date_font.get_height() + 3

        # ── Ticker (replaces static status line) ──
        if self._ticker_items:
            text = self._ticker_items[self._ticker_index]
            # Compute alpha from fade progress (map 0.0-1.0 to 0-255)
            alpha = int(self._ticker_fade * 255)
            # Blend color: DIM4 base, modulated by alpha
            r, g, b = DIM4
            faded_color = (r * alpha // 255, g * alpha // 255, b * alpha // 255)
            ticker_surf = status_font.render(text, False, faded_color)
            surface.blit(ticker_surf, (PAD_X, y))

        # Separator
        sep_y = HEADER_H - 1
        pygame.draw.line(surface, HAIRLINE,
                         (PAD_X, sep_y), (w - PAD_X, sep_y))

        # ── Quick access items ──
        self._render_items(surface, y_offset=HEADER_H)
