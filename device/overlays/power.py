"""Quick menu overlay shown on five-press power gesture."""
from __future__ import annotations

import pygame


class QuickMenu:
    """
    # WHY THIS EXISTS: shown on 5-press power gesture.
    # Presents SHUTDOWN / REBOOT / QUICK SETTINGS / HELP.
    # Replaces the old two-option PowerOverlay.
    """

    ITEMS = ["SHUTDOWN", "REBOOT", "QUICK SETTINGS", "HELP"]

    HELP_LINES = [
        ("SHORT PRESS", "NEXT ITEM"),
        ("DOUBLE PRESS", "SELECT"),
        ("LONG PRESS", "GO BACK"),
        ("TRIPLE PRESS", "AGENT"),
        ("5x PRESS", "THIS MENU"),
    ]

    def __init__(self, on_shutdown, on_reboot, on_cancel, on_open_settings=None):
        self._cursor = 0
        self._on_shutdown = on_shutdown
        self._on_reboot = on_reboot
        self._on_cancel = on_cancel
        self._on_open_settings = on_open_settings
        self._confirming = False  # "SHUTTING DOWN" / "REBOOTING" state
        self._confirm_label = ""
        self._showing_help = False
        self._fonts: dict[str, pygame.font.Font] = {}

    # ── Rendering ─────────────────────────────────────────────────

    def render(self, surface, tokens):
        surface.fill(tokens.BLACK)

        if self._confirming:
            self._render_confirming(surface, tokens)
            return

        if self._showing_help:
            self._render_help(surface, tokens)
            return

        self._render_menu(surface, tokens)

    def _render_menu(self, surface, tokens):
        title_font = self._font(tokens, "title")
        body_font = self._font(tokens, "body")
        hint_font = self._font(tokens, "hint")

        # Title
        header = title_font.render("QUICK MENU", False, tokens.WHITE)
        surface.blit(header, ((tokens.PHYSICAL_W - header.get_width()) // 2, 28))

        # Divider line below title
        div_y = 28 + header.get_height() + 8
        pygame.draw.line(surface, tokens.DIM3, (16, div_y), (tokens.PHYSICAL_W - 16, div_y))

        # Menu items
        item_h = 32
        start_y = div_y + 16
        pad_x = 20

        for i, label in enumerate(self.ITEMS):
            y = start_y + i * (item_h + 4)
            rect = pygame.Rect(pad_x, y, tokens.PHYSICAL_W - 2 * pad_x, item_h)

            if i == self._cursor:
                pygame.draw.rect(surface, tokens.WHITE, rect)
                color = tokens.BLACK
            else:
                pygame.draw.rect(surface, tokens.DIM4, rect, width=1)
                color = tokens.WHITE

            text = body_font.render(label, False, color)
            surface.blit(text, (rect.x + 10, rect.y + (item_h - text.get_height()) // 2))

        # Bottom hint
        hint = hint_font.render("SHORT:SCROLL \u00b7 DBL:SELECT \u00b7 LONG:CLOSE", False, tokens.DIM2)
        surface.blit(hint, ((tokens.PHYSICAL_W - hint.get_width()) // 2, tokens.PHYSICAL_H - hint.get_height() - 4))

    def _render_help(self, surface, tokens):
        title_font = self._font(tokens, "title")
        small_font = self._font(tokens, "small")
        hint_font = self._font(tokens, "hint")

        header = title_font.render("HELP", False, tokens.WHITE)
        surface.blit(header, ((tokens.PHYSICAL_W - header.get_width()) // 2, 28))

        div_y = 28 + header.get_height() + 8
        pygame.draw.line(surface, tokens.DIM3, (16, div_y), (tokens.PHYSICAL_W - 16, div_y))

        row_h = 30
        start_y = div_y + 16
        pad_x = 16

        for i, (gesture, action) in enumerate(self.HELP_LINES):
            y = start_y + i * row_h

            # Gesture label (left, bright)
            g_text = small_font.render(gesture, False, tokens.WHITE)
            surface.blit(g_text, (pad_x, y))

            # Action label (right-aligned, dimmer)
            a_text = small_font.render(action, False, tokens.DIM2)
            surface.blit(a_text, (tokens.PHYSICAL_W - pad_x - a_text.get_width(), y))

            # Separator line
            if i < len(self.HELP_LINES) - 1:
                line_y = y + row_h - 4
                pygame.draw.line(surface, tokens.HAIRLINE, (pad_x, line_y), (tokens.PHYSICAL_W - pad_x, line_y))

        # Bottom hint
        hint = hint_font.render("LONG:BACK", False, tokens.DIM2)
        surface.blit(hint, ((tokens.PHYSICAL_W - hint.get_width()) // 2, tokens.PHYSICAL_H - hint.get_height() - 4))

    def _render_confirming(self, surface, tokens):
        title_font = self._font(tokens, "title")
        small_font = self._font(tokens, "small")

        header = title_font.render(self._confirm_label, False, tokens.WHITE)
        hint = small_font.render("PLEASE WAIT...", False, tokens.DIM2)
        surface.blit(header, ((tokens.PHYSICAL_W - header.get_width()) // 2, 108))
        surface.blit(hint, ((tokens.PHYSICAL_W - hint.get_width()) // 2, 136))

    # ── Input ─────────────────────────────────────────────────────

    def handle_input(self, event):
        # VERIFIED: quick menu blocks underlying screen input while visible.
        if self._confirming:
            return True

        if self._showing_help:
            if event == "LONG_PRESS":
                self._showing_help = False
            return True

        if event == "SHORT_PRESS":
            self._cursor = (self._cursor + 1) % len(self.ITEMS)
        elif event == "DOUBLE_PRESS":
            self._select_current()
        elif event == "LONG_PRESS":
            self._on_cancel()
        return True

    def _select_current(self):
        item = self.ITEMS[self._cursor]
        if item == "SHUTDOWN":
            self._confirming = True
            self._confirm_label = "SHUTTING DOWN"
            self._on_shutdown()
        elif item == "REBOOT":
            self._confirming = True
            self._confirm_label = "REBOOTING"
            self._on_reboot()
        elif item == "QUICK SETTINGS":
            if self._on_open_settings:
                self._on_cancel()  # dismiss menu first
                self._on_open_settings()
        elif item == "HELP":
            self._showing_help = True

    # ── Font cache ────────────────────────────────────────────────

    def _font(self, tokens, key: str):
        if key in self._fonts:
            return self._fonts[key]
        try:
            font = pygame.font.Font(tokens.FONT_PATH, tokens.FONT_SIZES[key])
        except FileNotFoundError:
            font = pygame.font.SysFont("monospace", tokens.FONT_SIZES[key])
        self._fonts[key] = font
        return font


# Backward-compatible alias so existing imports still work.
PowerOverlay = QuickMenu
