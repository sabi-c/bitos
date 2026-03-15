"""BITOS Change PIN panel — 3-step PIN change flow with single-button entry."""
from __future__ import annotations

import time
import pygame

from display.theme import load_ui_font, merge_runtime_ui_settings
from display.tokens import BLACK, DIM3, HAIRLINE, PHYSICAL_H, PHYSICAL_W, WHITE, STATUS_BAR_H
from screens.base import BaseScreen
from storage.repository import DeviceRepository

_RED = (255, 0, 0)
_DEFAULT_PIN = "1234"

_STEP_LABELS = [
    "ENTER CURRENT PIN",
    "ENTER NEW PIN",
    "CONFIRM NEW PIN",
]


class ChangePinPanel(BaseScreen):
    """Three-step PIN change: verify current, enter new, confirm new."""

    _owns_status_bar = True

    def __init__(self, repository: DeviceRepository, on_back=None, ui_settings: dict | None = None):
        self._repo = repository
        self._on_back = on_back

        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_title = load_ui_font("title", self._ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)

        self._current_pin = self._load_pin()
        self._step = 0  # 0=verify current, 1=enter new, 2=confirm new
        self._entered: list[int] = []
        self._current_digit: int = 0
        self._cycling: bool = False
        self._new_pin: str = ""  # stored after step 1

        self._flash_until: float = 0.0
        self._success_until: float = 0.0

    def _load_pin(self) -> str:
        val = self._repo.get_setting("device_pin", default=_DEFAULT_PIN)
        if val and isinstance(val, str) and len(val) >= 4:
            return val
        return _DEFAULT_PIN

    def on_enter(self):
        self._current_pin = self._load_pin()
        self._step = 0
        self._entered.clear()
        self._current_digit = 0
        self._cycling = False
        self._new_pin = ""

    def handle_action(self, action: str):
        now = time.time()

        # During success flash, ignore input
        if now < self._success_until:
            return

        # During error flash, ignore input
        if now < self._flash_until:
            return

        if action == "SHORT_PRESS":
            self._cycling = True
            self._current_digit = (self._current_digit + 1) % 10
        elif action == "LONG_PRESS":
            self._entered.append(self._current_digit)
            self._current_digit = 0
            self._cycling = False
            if len(self._entered) == 4:
                self._on_step_complete()
        elif action == "DOUBLE_PRESS":
            if self._entered:
                self._entered.pop()
                self._current_digit = 0
                self._cycling = False
            else:
                # No digits entered: go back
                if self._on_back:
                    self._on_back()

    def handle_input(self, event: pygame.event.Event):
        if event.type != pygame.KEYDOWN:
            return
        if event.key == pygame.K_SPACE:
            self.handle_action("SHORT_PRESS")
        elif event.key == pygame.K_RETURN:
            self.handle_action("LONG_PRESS")
        elif event.key in (pygame.K_BACKSPACE, pygame.K_ESCAPE):
            self.handle_action("DOUBLE_PRESS")

    def render(self, surface: pygame.Surface):
        now = time.time()
        is_flashing = now < self._flash_until
        is_success = now < self._success_until
        bg = _RED if is_flashing else BLACK
        surface.fill(bg)

        text_color = WHITE

        # ── Status bar ──
        bar_bg = WHITE if not is_flashing else _RED
        bar_fg = BLACK if not is_flashing else WHITE
        pygame.draw.rect(surface, bar_bg, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        title = self._font_small.render("CHANGE PIN", False, bar_fg)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))

        # ── Step label ──
        step_label = _STEP_LABELS[self._step] if self._step < 3 else "DONE"
        if is_success:
            step_label = "PIN CHANGED!"
        step_surf = self._font_body.render(step_label, False, text_color)
        step_x = (PHYSICAL_W - step_surf.get_width()) // 2
        step_y = STATUS_BAR_H + 30
        surface.blit(step_surf, (step_x, step_y))

        # ── Step indicator (1/3, 2/3, 3/3) ──
        indicator = f"STEP {self._step + 1}/3"
        if is_success:
            indicator = ""
        if indicator:
            ind_surf = self._font_small.render(indicator, False, DIM3 if not is_flashing else text_color)
            ind_x = (PHYSICAL_W - ind_surf.get_width()) // 2
            surface.blit(ind_surf, (ind_x, step_y + step_surf.get_height() + 6))

        # ── PIN dots ──
        pin_y = step_y + step_surf.get_height() + 30
        if not is_success:
            self._draw_pin_dots(surface, pin_y, text_color)

        # ── Separator ──
        sep_y = pin_y + 24
        line_color = HAIRLINE if not is_flashing else text_color
        pygame.draw.line(surface, line_color, (40, sep_y), (PHYSICAL_W - 40, sep_y))

        # ── Hints ──
        hint1 = self._font_hint.render("SHORT:NEXT \u00b7 LONG:ENTER", False, DIM3 if not is_flashing else text_color)
        hint1_x = (PHYSICAL_W - hint1.get_width()) // 2
        hint1_y = sep_y + 8
        surface.blit(hint1, (hint1_x, hint1_y))

        hint2 = self._font_hint.render("DBL:DELETE/BACK", False, DIM3 if not is_flashing else text_color)
        hint2_x = (PHYSICAL_W - hint2.get_width()) // 2
        hint2_y = hint1_y + hint1.get_height() + 4
        surface.blit(hint2, (hint2_x, hint2_y))

    def _draw_pin_dots(self, surface: pygame.Surface, y: int, color):
        parts = []
        for _d in self._entered:
            parts.append("\u25cf")
        if len(self._entered) < 4:
            if self._cycling:
                parts.append(f"[{self._current_digit}]")
            else:
                parts.append("[ ]")
        remaining = 4 - len(self._entered) - (1 if len(self._entered) < 4 else 0)
        for _ in range(remaining):
            parts.append("_")
        display = "  ".join(parts)
        pin_surf = self._font_body.render(display, False, color)
        pin_x = (PHYSICAL_W - pin_surf.get_width()) // 2
        surface.blit(pin_surf, (pin_x, y))

    def _on_step_complete(self):
        entered_str = "".join(str(d) for d in self._entered)

        if self._step == 0:
            # Verify current PIN
            if entered_str == self._current_pin:
                self._step = 1
                self._entered.clear()
                self._current_digit = 0
                self._cycling = False
            else:
                self._flash_until = time.time() + 0.3
                self._entered.clear()
                self._current_digit = 0
                self._cycling = False

        elif self._step == 1:
            # Store new PIN candidate
            self._new_pin = entered_str
            self._step = 2
            self._entered.clear()
            self._current_digit = 0
            self._cycling = False

        elif self._step == 2:
            # Confirm new PIN
            if entered_str == self._new_pin:
                self._repo.set_setting("device_pin", self._new_pin)
                self._current_pin = self._new_pin
                self._success_until = time.time() + 0.5
                # Go back after brief success flash
                if self._on_back:
                    self._on_back()
            else:
                self._flash_until = time.time() + 0.3
                self._entered.clear()
                self._current_digit = 0
                self._cycling = False
