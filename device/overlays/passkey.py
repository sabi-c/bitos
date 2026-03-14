"""Passkey pairing overlay shown during BLE pairing mode."""
from __future__ import annotations

from typing import Callable

import pygame


class PasskeyOverlay:
    """Shows during BLE pairing. Full screen, blocks input."""

    def __init__(self, code: str, timeout_s: int = 120, on_timeout: Callable[[], None] | None = None):
        self._code = str(code).zfill(6)
        self._remaining_ms = max(1, int(timeout_s * 1000))
        self._on_timeout = on_timeout

    def render(self, surface, tokens) -> None:
        surface.fill(tokens.BLACK)

        title_font = self._font(tokens, "title")
        body_font = self._font(tokens, "body")
        small_font = self._font(tokens, "small")

        header = title_font.render("PAIRING MODE", False, tokens.WHITE)
        code = title_font.render(self._code, False, tokens.WHITE)
        hint = body_font.render("TYPE THIS ON YOUR PHONE", False, tokens.DIM2)
        seconds = max(0, self._remaining_ms // 1000)
        timer = small_font.render(f"TIME LEFT {seconds:03d}s", False, tokens.DIM3)

        surface.blit(header, ((tokens.PHYSICAL_W - header.get_width()) // 2, 60))
        surface.blit(code, ((tokens.PHYSICAL_W - code.get_width()) // 2, 118))
        surface.blit(hint, ((tokens.PHYSICAL_W - hint.get_width()) // 2, 168))
        surface.blit(timer, ((tokens.PHYSICAL_W - timer.get_width()) // 2, 188))

    def tick(self, dt_ms) -> bool:
        self._remaining_ms -= max(0, int(dt_ms))
        if self._remaining_ms > 0:
            return True
        self._remaining_ms = 0
        if self._on_timeout:
            self._on_timeout()
        return False

    def handle_input(self, _action: str) -> bool:
        return True

    def _font(self, tokens, key: str):
        try:
            return pygame.font.Font(tokens.FONT_PATH, tokens.FONT_SIZES[key])
        except FileNotFoundError:
            return pygame.font.SysFont("monospace", tokens.FONT_SIZES[key])
