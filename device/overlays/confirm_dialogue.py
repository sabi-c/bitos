"""Two-button confirmation dialogue overlay — 1-bit UI kit style.

Renders a centered card with title bar, message, and CANCEL/CONFIRM buttons.
Supports destructive mode (red confirm button).

Gestures:
- SHORT_PRESS / TRIPLE_PRESS: toggle between cancel and confirm
- DOUBLE_PRESS: activate focused button
- LONG_PRESS: always cancels (safe escape)

Duck-types with the overlay slot in ScreenManager (tick/handle_action/render/dismissed).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pygame

from display.tokens import (
    BLACK, WHITE, DIM2, DIM3, HAIRLINE,
    PHYSICAL_W, PHYSICAL_H, SAFE_INSET,
    FONT_PATH, FONT_SIZES,
)

# ── Colours ──────────────────────────────────────────────────────────

RED = (244, 68, 68)
DARK_RED = (140, 30, 30)

# ── Layout constants ─────────────────────────────────────────────────

CARD_W = PHYSICAL_W - SAFE_INSET * 2  # 208px
OUTER_BORDER = 3
TITLE_BAR_H = 24
BUTTON_H = 32
DIVIDER_H = 2
MSG_PAD = 10
BUTTON_PAD = 6


@dataclass
class ConfirmDialogue:
    """Two-button confirm/cancel dialogue."""

    title: str = "CONFIRM"
    message: str = ""
    cancel_label: str = "CANCEL"
    confirm_label: str = "OK"
    destructive: bool = False
    on_confirm: Callable[[], None] | None = None
    on_cancel: Callable[[], None] | None = None
    timeout_ms: int = 60_000
    elapsed_ms: int = 0
    _selected: int = field(default=0, init=False)     # 0=cancel, 1=confirm
    _dismissed: bool = field(default=False, init=False)
    _result: str | None = field(default=None, init=False)
    _fonts: dict[str, pygame.font.Font] = field(default_factory=dict, init=False, repr=False)

    @property
    def dismissed(self) -> bool:
        return self._dismissed

    @property
    def result(self) -> str | None:
        """'confirm', 'cancel', or None if still active."""
        return self._result

    # ── Lifecycle ────────────────────────────────────────────────────

    def tick(self, dt_ms: int) -> bool:
        """Returns True while overlay should stay alive."""
        if self._dismissed:
            return False
        self.elapsed_ms += max(0, int(dt_ms))
        if self.elapsed_ms >= self.timeout_ms:
            self._do_cancel()
            return False
        return True

    def handle_action(self, action: str) -> bool:
        """Consume all gestures while active."""
        if self._dismissed:
            return False

        if action in ("SHORT_PRESS", "TRIPLE_PRESS"):
            # Toggle selection
            self._selected = 1 - self._selected
            return True

        if action == "DOUBLE_PRESS":
            # Activate focused button
            if self._selected == 0:
                self._do_cancel()
            else:
                self._do_confirm()
            return True

        if action == "LONG_PRESS":
            # Always cancel (safe escape)
            self._do_cancel()
            return True

        # Consume all other actions
        if action in ("HOLD_START", "HOLD_END"):
            return True

        return True  # consume everything while visible

    def render(self, surface: pygame.Surface) -> None:
        """Draw the confirmation dialogue card."""
        if self._dismissed:
            return

        font_small = self._font("small")
        font_hint = self._font("hint")
        font_body = self._font("body")

        # Dim background (70% black)
        dim = pygame.Surface((PHYSICAL_W, PHYSICAL_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 179))
        surface.blit(dim, (0, 0))

        # Calculate card height dynamically
        msg_lines = self._wrap_text(self.message, font_hint, CARD_W - MSG_PAD * 2 - OUTER_BORDER * 2) if self.message else []
        msg_lines = msg_lines[:3]
        msg_area_h = max(0, len(msg_lines) * (font_hint.get_height() + 3) + MSG_PAD * 2) if msg_lines else 0

        card_h = OUTER_BORDER * 2 + TITLE_BAR_H + msg_area_h + DIVIDER_H + BUTTON_H + BUTTON_PAD * 2
        card_x = SAFE_INSET
        card_y = (PHYSICAL_H - card_h) // 2

        # Card background
        card_rect = pygame.Rect(card_x, card_y, CARD_W, card_h)
        pygame.draw.rect(surface, BLACK, card_rect)

        # 3px white outer border
        pygame.draw.rect(surface, WHITE, card_rect, OUTER_BORDER)

        inner_x = card_x + OUTER_BORDER
        inner_w = CARD_W - OUTER_BORDER * 2
        y = card_y + OUTER_BORDER

        # ── Title bar (white background, black text) ────────────────
        title_rect = pygame.Rect(inner_x, y, inner_w, TITLE_BAR_H)
        pygame.draw.rect(surface, WHITE, title_rect)
        title_surf = font_small.render(self.title, True, BLACK)
        title_text_y = y + (TITLE_BAR_H - title_surf.get_height()) // 2
        surface.blit(title_surf, (inner_x + 8, title_text_y))
        y += TITLE_BAR_H

        # ── Message area ────────────────────────────────────────────
        if msg_lines:
            y += MSG_PAD
            for line in msg_lines:
                line_surf = font_hint.render(line, True, DIM2)
                surface.blit(line_surf, (inner_x + MSG_PAD, y))
                y += font_hint.get_height() + 3
            y += MSG_PAD - 3  # remove trailing 3px

        # ── Divider ─────────────────────────────────────────────────
        pygame.draw.rect(surface, WHITE, pygame.Rect(inner_x, y, inner_w, DIVIDER_H))
        y += DIVIDER_H

        # ── Buttons ─────────────────────────────────────────────────
        y += BUTTON_PAD
        btn_w = (inner_w - BUTTON_PAD * 3) // 2
        cancel_x = inner_x + BUTTON_PAD
        confirm_x = cancel_x + btn_w + BUTTON_PAD

        # Cancel button
        self._draw_button(
            surface, cancel_x, y, btn_w, BUTTON_H,
            self.cancel_label, font_small,
            focused=(self._selected == 0),
            destructive=False,
        )

        # Confirm button
        self._draw_button(
            surface, confirm_x, y, btn_w, BUTTON_H,
            self.confirm_label, font_small,
            focused=(self._selected == 1),
            destructive=self.destructive,
        )

    def _draw_button(
        self, surface: pygame.Surface,
        x: int, y: int, w: int, h: int,
        label: str, font: pygame.font.Font,
        focused: bool, destructive: bool,
    ) -> None:
        btn_rect = pygame.Rect(x, y, w, h)

        if focused:
            # White fill + black text (or dark red if destructive)
            pygame.draw.rect(surface, WHITE, btn_rect)
            text_color = DARK_RED if destructive else BLACK
        else:
            # Outlined
            pygame.draw.rect(surface, WHITE, btn_rect, 1)
            text_color = RED if destructive else WHITE

        label_surf = font.render(label, True, text_color)
        label_rect = label_surf.get_rect(center=btn_rect.center)
        surface.blit(label_surf, label_rect)

    # ── Internal ─────────────────────────────────────────────────────

    def _do_confirm(self) -> None:
        self._dismissed = True
        self._result = "confirm"
        if self.on_confirm:
            self.on_confirm()

    def _do_cancel(self) -> None:
        self._dismissed = True
        self._result = "cancel"
        if self.on_cancel:
            self.on_cancel()

    def _font(self, key: str) -> pygame.font.Font:
        if key in self._fonts:
            return self._fonts[key]
        try:
            font = pygame.font.Font(FONT_PATH, FONT_SIZES[key])
        except FileNotFoundError:
            font = pygame.font.SysFont("monospace", FONT_SIZES[key])
        self._fonts[key] = font
        return font

    @staticmethod
    def _wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            test = f"{current} {word}".strip()
            if font.size(test)[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines or [""]
