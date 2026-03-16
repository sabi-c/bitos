"""Power action overlay shown during five-press gesture."""
from __future__ import annotations

import pygame


class PowerOverlay:
    """
    # WHY THIS EXISTS: shown on 5-press power gesture.
    # Presents SHUTDOWN vs REBOOT choice, blocks all input.
    """

    def __init__(self, on_shutdown, on_reboot, on_cancel):
        self._choice = 0  # 0=shutdown, 1=reboot
        self._on_shutdown = on_shutdown
        self._on_reboot = on_reboot
        self._on_cancel = on_cancel
        self._saving = False
        self._saved = False
        self._fonts: dict[str, pygame.font.Font] = {}

    def render(self, surface, tokens):
        surface.fill(tokens.BLACK)
        title_font = self._font(tokens, "title")
        body_font = self._font(tokens, "body")
        small_font = self._font(tokens, "small")

        if self._saving:
            header = title_font.render("SHUTTING DOWN", False, tokens.WHITE)
            hint = small_font.render("PLEASE WAIT...", False, tokens.DIM2)
            surface.blit(header, ((tokens.PHYSICAL_W - header.get_width()) // 2, 108))
            surface.blit(hint, ((tokens.PHYSICAL_W - hint.get_width()) // 2, 136))
            return

        header = title_font.render("POWER", False, tokens.WHITE)
        surface.blit(header, ((tokens.PHYSICAL_W - header.get_width()) // 2, 32))

        row_w = 108
        row_h = 28
        left_x = 8
        right_x = tokens.PHYSICAL_W - row_w - 8
        y = 108

        self._render_choice(surface, body_font, tokens, "SHUTDOWN", left_x, y, row_w, row_h, selected=self._choice == 0)
        self._render_choice(surface, body_font, tokens, "REBOOT", right_x, y, row_w, row_h, selected=self._choice == 1)

        hint_font = self._font(tokens, "hint")
        hint = hint_font.render("SHORT:TOGGLE \u00b7 DBL:CONFIRM \u00b7 LONG:CANCEL", False, tokens.DIM2)
        surface.blit(hint, ((tokens.PHYSICAL_W - hint.get_width()) // 2, tokens.PHYSICAL_H - hint.get_height() - 2))

    def handle_input(self, event):
        # VERIFIED: power overlay blocks underlying screen input while visible.
        if self._saving:
            return True
        if event == "SHORT_PRESS":
            self._choice = 1 - self._choice
        elif event == "DOUBLE_PRESS":
            self._saving = True
            if self._choice == 0:
                self._on_shutdown()
            else:
                self._on_reboot()
            self._saved = True
        elif event == "LONG_PRESS":
            self._on_cancel()
        return True

    def _render_choice(self, surface, font, tokens, label: str, x: int, y: int, w: int, h: int, selected: bool):
        if selected:
            pygame.draw.rect(surface, tokens.WHITE, pygame.Rect(x, y, w, h))
            color = tokens.BLACK
        else:
            pygame.draw.rect(surface, tokens.WHITE, pygame.Rect(x, y, w, h), width=1)
            color = tokens.WHITE
        text = font.render(label, False, color)
        surface.blit(text, (x + (w - text.get_width()) // 2, y + (h - text.get_height()) // 2))

    def _font(self, tokens, key: str):
        if key in self._fonts:
            return self._fonts[key]
        try:
            font = pygame.font.Font(tokens.FONT_PATH, tokens.FONT_SIZES[key])
        except FileNotFoundError:
            font = pygame.font.SysFont("monospace", tokens.FONT_SIZES[key])
        self._fonts[key] = font
        return font
