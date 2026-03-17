"""Widget system for BITOS home screen — bordered info cards."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pygame

from display.tokens import WHITE, DIM2, DIM3, GRAY_33, HAIRLINE


@dataclass
class Widget:
    """A single info card widget (time, weather, unread count, etc.)."""

    key: str          # unique ID ("time", "weather", "unread")
    label: str        # top label ("TIME", "WEATHER")
    value: str        # main display value ("09:41", "72F", "5")
    subtitle: str = ""  # optional bottom text ("BURBANK", etc.)

    def render(
        self,
        surface: pygame.Surface,
        x: int,
        y: int,
        w: int,
        h: int,
        focused: bool = False,
        fonts: dict[str, pygame.font.Font] | None = None,
    ) -> None:
        """Draw bordered card. Focused = white border + bright text, else dim."""
        fonts = fonts or {}
        font_hint = fonts.get("hint")
        font_small = fonts.get("small")

        border_color = WHITE if focused else GRAY_33
        value_color = WHITE if focused else DIM2
        label_color = DIM3
        subtitle_color = DIM3

        # Border rectangle
        rect = pygame.Rect(x, y, w, h)
        pygame.draw.rect(surface, border_color, rect, 1)

        pad = 3

        # Label at top
        if font_hint and self.label:
            lbl = font_hint.render(self.label, False, label_color)
            surface.blit(lbl, (x + (w - lbl.get_width()) // 2, y + pad))

        # Value centered
        if font_small and self.value:
            val = font_small.render(self.value, False, value_color)
            val_y = y + (h - val.get_height()) // 2
            surface.blit(val, (x + (w - val.get_width()) // 2, val_y))

        # Subtitle at bottom
        if font_hint and self.subtitle:
            sub = font_hint.render(self.subtitle, False, subtitle_color)
            surface.blit(sub, (x + (w - sub.get_width()) // 2, y + h - sub.get_height() - pad))


class WidgetStrip:
    """Horizontal row of Widget cards with focus management."""

    def __init__(self, widgets: list[Widget] | None = None):
        self._widgets: list[Widget] = list(widgets) if widgets else []
        self._focus_index: int = 0

    @property
    def widgets(self) -> list[Widget]:
        return self._widgets

    @property
    def focus_index(self) -> int:
        return self._focus_index

    def move_focus(self, direction: int) -> None:
        """Cycle focus left/right among widgets."""
        if not self._widgets:
            return
        step = 1 if direction > 0 else -1
        self._focus_index = (self._focus_index + step) % len(self._widgets)

    def update_widget(self, key: str, value: str | None = None, subtitle: str | None = None) -> bool:
        """Update a widget's value and/or subtitle by key. Returns True if found."""
        for w in self._widgets:
            if w.key == key:
                if value is not None:
                    w.value = value
                if subtitle is not None:
                    w.subtitle = subtitle
                return True
        return False

    def render(
        self,
        surface: pygame.Surface,
        y: int,
        width: int,
        height: int = 50,
        fonts: dict[str, pygame.font.Font] | None = None,
    ) -> None:
        """Render all widgets in an equally-spaced horizontal row."""
        if not self._widgets:
            return
        n = len(self._widgets)
        gap = 4
        total_gap = gap * (n - 1)
        w_each = (width - total_gap) // n
        x = 0
        for i, widget in enumerate(self._widgets):
            focused = i == self._focus_index
            widget.render(surface, x, y, w_each, height, focused=focused, fonts=fonts)
            x += w_each + gap
