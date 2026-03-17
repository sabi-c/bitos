"""On-screen QWERTY keyboard widget for text input.

Renders at the bottom portion of the screen. Supports alpha (QWERTY)
and numeric/symbol modes, shift toggle, and configurable callbacks.

Navigation (single button):
- SHORT_PRESS: move right (wraps to next row)
- TRIPLE_PRESS: move left (wraps to previous row)
- LONG_PRESS: move down one row
- DOUBLE_PRESS: activate focused key
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pygame

from display.tokens import (
    BLACK, WHITE, DIM2, DIM3, DIM4, HAIRLINE,
    PHYSICAL_W, PHYSICAL_H,
    FONT_PATH, FONT_SIZES,
)

# ── Keyboard layouts ─────────────────────────────────────────────

ALPHA_ROWS = [
    list("QWERTYUIOP"),
    list("ASDFGHJKL"),
    ["SHF"] + list("ZXCVBNM") + ["DEL"],
    ["123", "SPACE", "ENTER"],
]

NUMERIC_ROWS = [
    list("1234567890"),
    list("!@#$%^&*("),
    [")_+-=[]{}|"],
    ["ABC", "SPACE", "ENTER"],
]
# Flatten row 2 of numeric into individual chars
NUMERIC_ROWS[2] = list(")_+-=[]{}|")

# ── Constants ────────────────────────────────────────────────────

KB_BG = (5, 5, 5)
KEY_BORDER = DIM4
KEY_TEXT = DIM2
FOCUSED_BG = WHITE
FOCUSED_TEXT = BLACK
TEXT_FIELD_BORDER = WHITE
KEY_H = 22
KEY_PAD = 2
TEXT_FIELD_H = 24
TEXT_FIELD_PAD = 6
FONT_KEY = "hint"    # 11px — fits key caps
FONT_FIELD = "small"  # 13px — text input


@dataclass
class OnScreenKeyboard:
    """Reusable keyboard overlay component."""

    prompt: str = ""
    initial_text: str = ""
    on_done: Callable[[str], None] | None = None
    on_cancel: Callable[[], None] | None = None

    # Internal state
    _text: str = field(default="", init=False)
    _active: bool = field(default=True, init=False)
    _shifted: bool = field(default=False, init=False)
    _numeric: bool = field(default=False, init=False)
    _row: int = field(default=0, init=False)
    _col: int = field(default=0, init=False)
    _fonts: dict[str, pygame.font.Font] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self):
        self._text = self.initial_text

    @property
    def text(self) -> str:
        return self._text

    @property
    def active(self) -> bool:
        return self._active

    @property
    def rows(self) -> list[list[str]]:
        return NUMERIC_ROWS if self._numeric else ALPHA_ROWS

    @property
    def focused_key(self) -> str:
        rows = self.rows
        row = rows[self._row]
        return row[self._col]

    def tick(self, dt_ms: int) -> bool:
        """Returns True while keyboard is active, False when dismissed."""
        return self._active

    def handle_action(self, action: str) -> bool:
        """Consume all actions while keyboard is up. Returns True if consumed."""
        if not self._active:
            return False

        if action == "SHORT_PRESS":
            self._move_right()
            return True

        if action == "TRIPLE_PRESS":
            self._move_left()
            return True

        if action == "LONG_PRESS":
            self._move_down()
            return True

        if action == "DOUBLE_PRESS":
            self._activate_key()
            return True

        # Consume hold events too
        if action in ("HOLD_START", "HOLD_END", "POWER_GESTURE"):
            return True

        return False

    def render(self, surface: pygame.Surface) -> None:
        """Render keyboard at the bottom of the screen."""
        if not self._active:
            return

        font_key = self._font(FONT_KEY)
        font_field = self._font(FONT_FIELD)
        rows = self.rows

        # Calculate total keyboard height
        num_rows = len(rows)
        kb_h = TEXT_FIELD_H + TEXT_FIELD_PAD + (KEY_H + KEY_PAD) * num_rows + KEY_PAD * 2
        kb_y = PHYSICAL_H - kb_h

        # Dark background
        bg_rect = pygame.Rect(0, kb_y, PHYSICAL_W, kb_h)
        pygame.draw.rect(surface, KB_BG, bg_rect)

        # Text field
        field_x = KEY_PAD * 2
        field_y = kb_y + KEY_PAD
        field_w = PHYSICAL_W - KEY_PAD * 4
        field_rect = pygame.Rect(field_x, field_y, field_w, TEXT_FIELD_H)
        pygame.draw.rect(surface, BLACK, field_rect)
        pygame.draw.rect(surface, TEXT_FIELD_BORDER, field_rect, 1)

        # Prompt label + text
        display_text = self._text
        if self.prompt:
            label_surf = font_field.render(self.prompt + " ", False, DIM3)
            surface.blit(label_surf, (field_x + 4, field_y + (TEXT_FIELD_H - label_surf.get_height()) // 2))
            text_x = field_x + 4 + label_surf.get_width()
        else:
            text_x = field_x + 4

        # Render text with cursor
        text_surf = font_field.render(display_text + "_", False, WHITE)
        text_y = field_y + (TEXT_FIELD_H - text_surf.get_height()) // 2
        # Clip to field
        max_text_w = field_x + field_w - text_x - 4
        if text_surf.get_width() > max_text_w:
            clip_rect = pygame.Rect(text_surf.get_width() - max_text_w, 0, max_text_w, text_surf.get_height())
            surface.blit(text_surf, (text_x, text_y), clip_rect)
        else:
            surface.blit(text_surf, (text_x, text_y))

        # Key rows
        row_y = field_y + TEXT_FIELD_H + TEXT_FIELD_PAD

        for r_idx, row in enumerate(rows):
            total_keys = len(row)
            # Calculate key widths — special keys get more space
            key_widths = self._calc_key_widths(row, PHYSICAL_W - KEY_PAD * 2)
            x = KEY_PAD

            for c_idx, key_label in enumerate(row):
                kw = key_widths[c_idx]
                is_focused = (r_idx == self._row and c_idx == self._col)

                key_rect = pygame.Rect(x, row_y, kw - 1, KEY_H)

                if is_focused:
                    pygame.draw.rect(surface, FOCUSED_BG, key_rect)
                    color = FOCUSED_TEXT
                else:
                    pygame.draw.rect(surface, KB_BG, key_rect)
                    pygame.draw.rect(surface, KEY_BORDER, key_rect, 1)
                    color = KEY_TEXT

                # Render label
                display_label = self._display_label(key_label)
                lbl_surf = font_key.render(display_label, False, color)
                lbl_x = x + (kw - 1 - lbl_surf.get_width()) // 2
                lbl_y = row_y + (KEY_H - lbl_surf.get_height()) // 2
                surface.blit(lbl_surf, (lbl_x, lbl_y))

                x += kw

            row_y += KEY_H + KEY_PAD

    # ── Private helpers ──────────────────────────────────────────

    def _move_right(self) -> None:
        rows = self.rows
        self._col += 1
        if self._col >= len(rows[self._row]):
            # Wrap to next row
            self._row = (self._row + 1) % len(rows)
            self._col = 0

    def _move_left(self) -> None:
        rows = self.rows
        self._col -= 1
        if self._col < 0:
            # Wrap to previous row
            self._row = (self._row - 1) % len(rows)
            self._col = len(rows[self._row]) - 1

    def _move_down(self) -> None:
        rows = self.rows
        self._row = (self._row + 1) % len(rows)
        if self._col >= len(rows[self._row]):
            self._col = len(rows[self._row]) - 1

    def _activate_key(self) -> None:
        key = self.focused_key

        if key == "ENTER":
            self._active = False
            if self.on_done:
                self.on_done(self._text)
            return

        if key == "DEL":
            if self._text:
                self._text = self._text[:-1]
            return

        if key == "SHF":
            self._shifted = not self._shifted
            return

        if key == "SPACE":
            self._text += " "
            return

        if key == "123":
            self._numeric = True
            self._row = 0
            self._col = 0
            return

        if key == "ABC":
            self._numeric = False
            self._row = 0
            self._col = 0
            return

        # Regular character
        ch = key.lower() if not self._shifted else key.upper()
        if self._numeric:
            ch = key  # symbols are literal
        self._text += ch

        # Auto-unshift after one character
        if self._shifted:
            self._shifted = False

    def _display_label(self, key: str) -> str:
        """Return the display string for a key, respecting shift state."""
        if key == "SHF":
            return "SHF" if not self._shifted else "SHF"
        if key == "DEL":
            return "DEL"
        if key == "SPACE":
            return "___"
        if key == "ENTER":
            return "OK"
        if key in ("123", "ABC"):
            return key
        # Single char keys
        if len(key) == 1:
            if self._numeric:
                return key
            return key.upper() if self._shifted else key.lower()
        return key

    def _calc_key_widths(self, row: list[str], total_w: int) -> list[int]:
        """Calculate pixel widths for each key in a row."""
        # Special keys get 1.5x width
        weights = []
        for key in row:
            if key in ("SHF", "DEL", "ENTER", "123", "ABC"):
                weights.append(1.5)
            elif key == "SPACE":
                weights.append(3.0)
            else:
                weights.append(1.0)
        total_weight = sum(weights)
        widths = [int(total_w * w / total_weight) for w in weights]
        # Fix rounding: give remainder to last key
        remainder = total_w - sum(widths)
        widths[-1] += remainder
        return widths

    def _font(self, key: str) -> pygame.font.Font:
        if key in self._fonts:
            return self._fonts[key]
        try:
            font = pygame.font.Font(FONT_PATH, FONT_SIZES[key])
        except FileNotFoundError:
            font = pygame.font.SysFont("monospace", FONT_SIZES[key])
        self._fonts[key] = font
        return font
