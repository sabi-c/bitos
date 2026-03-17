"""Test typewriter overlay — renders sample text with custom config, auto-dismisses."""

from __future__ import annotations

import time
import pygame

from display.typewriter import TypewriterRenderer, TypewriterConfig
from display.theme import get_font
from display.tokens import PHYSICAL_W, PHYSICAL_H


class TestTypewriterOverlay:
    """Overlay that renders a typewriter test, auto-dismisses when done + 2s."""

    def __init__(self, text: str, config: dict, on_dismiss: callable):
        self._text = text
        self._config = TypewriterConfig.from_dict(config)
        self._tw = TypewriterRenderer(text, config=self._config)
        self._on_dismiss = on_dismiss
        self._finished_at: float | None = None
        self._dismissed = False

    def tick(self, dt: float) -> None:
        if self._dismissed:
            return
        self._tw.update(dt)
        if self._tw.finished and self._finished_at is None:
            self._finished_at = time.time()
        # Auto-dismiss 2s after typewriter finishes
        if self._finished_at and time.time() - self._finished_at > 2.0:
            self._dismissed = True
            if self._on_dismiss:
                self._on_dismiss()

    def render(self, surface: pygame.Surface) -> None:
        surface.fill((0, 0, 0))
        font = get_font(9)
        WHITE = (255, 255, 255)
        DIM2 = (100, 100, 100)

        # Title
        title_font = get_font(11)
        title = title_font.render("TYPEWRITER TEST", False, DIM2)
        surface.blit(title, ((PHYSICAL_W - title.get_width()) // 2, 8))

        # Visible text with word wrapping
        visible = self._tw.get_visible_text()
        y = 32
        max_w = PHYSICAL_W - 16
        words = visible.split(" ")
        line = ""
        for word in words:
            test = (line + " " + word).strip()
            if font.size(test)[0] > max_w and line:
                surf = font.render(line, False, WHITE)
                surface.blit(surf, (8, y))
                y += font.get_height() + 2
                line = word
            else:
                line = test
        if line:
            surf = font.render(line, False, WHITE)
            surface.blit(surf, (8, y))

        # Config info at bottom
        info_font = get_font(7)
        info = f"{self._config.base_speed_ms:.0f}ms  jit={self._config.jitter_amount:.2f}  punc={self._config.punctuation_multiplier:.1f}x"
        info_surf = info_font.render(info, False, DIM2)
        surface.blit(info_surf, ((PHYSICAL_W - info_surf.get_width()) // 2, PHYSICAL_H - info_surf.get_height() - 4))

    def handle_action(self, event: str) -> bool:
        if event == "LONG_PRESS":
            self._dismissed = True
            if self._on_dismiss:
                self._on_dismiss()
        return True  # consume all input while overlay is active
