"""BLE LESC passkey overlay shown during companion pairing."""
from __future__ import annotations

from typing import Callable

import pygame

from display.tokens import (
    BLACK, WHITE, DIM2, DIM3, HAIRLINE,
    PHYSICAL_W, PHYSICAL_H, STATUS_BAR_H,
    FONT_PATH, FONT_SIZES,
)


def _format_pin(code: str) -> str:
    """Format '123456' as '123 456' for readability."""
    code = code.zfill(6)
    return f"{code[:3]} {code[3:]}"


class PasskeyOverlay:
    """
    # WHY THIS EXISTS: shows BLE LESC passkey during pairing.
    # Blocks all other input while active.
    # Dismissed by BLE pairing agent on success/failure.
    """

    def __init__(
        self,
        passkey: str,
        on_confirmed: Callable[[], None] | None = None,
        on_timeout: Callable[[], None] | None = None,
        on_cancelled: Callable[[], None] | None = None,
        timeout_seconds: int = 30,
    ):
        self._passkey = str(passkey).zfill(6)
        self._on_confirmed = on_confirmed
        self._on_timeout = on_timeout
        self._on_cancelled = on_cancelled
        self._timeout_s = max(1, timeout_seconds)
        self._elapsed = 0.0
        self._state = "showing"  # showing / confirmed / failed / timeout
        self._blink = True
        self._blink_timer = 0.0
        self._fonts: dict[str, pygame.font.Font] = {}

    # ── Render ────────────────────────────────────────────────────

    def render(self, surface: pygame.Surface, tokens=None) -> None:
        # VERIFIED: BLE pairing displays PIN code prominently until confirmed/cancelled/timeout.
        surface.fill(BLACK)

        title_font = self._font("title")
        body_font = self._font("body")
        small_font = self._font("small")
        hint_font = self._font("hint")

        # ── Status bar: 18px inverted ──
        pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        dot = small_font.render("\u25cf PAIRING", False, BLACK)
        surface.blit(dot, (6, (STATUS_BAR_H - dot.get_height()) // 2))

        # ── State-dependent body ──
        if self._state == "confirmed":
            self._render_result(surface, body_font, small_font, "PAIRED", DIM2)
            return
        if self._state == "failed":
            self._render_result(surface, body_font, small_font, "CANCELLED", DIM2)
            return
        if self._state == "timeout":
            self._render_result(surface, body_font, small_font, "TIMEOUT", DIM2)
            return

        # ── "PAIR REQUEST" label ──
        label = body_font.render("PAIR REQUEST", False, DIM3)
        surface.blit(label, ((PHYSICAL_W - label.get_width()) // 2, 70))

        # ── PIN display: "123 456" ──
        pin_text = _format_pin(self._passkey)
        pin_surface = title_font.render(pin_text, False, WHITE)
        pin_x = (PHYSICAL_W - pin_surface.get_width()) // 2
        pin_y = 100
        surface.blit(pin_surface, (pin_x, pin_y))

        # ── Blinking cursor below PIN ──
        if self._blink:
            cursor_w = pin_surface.get_width()
            cursor_y = pin_y + pin_surface.get_height() + 4
            pygame.draw.rect(surface, WHITE, (pin_x, cursor_y, cursor_w, 2))

        # ── Countdown ──
        remaining = max(0, int(self._timeout_s - self._elapsed))
        timer = small_font.render(f"{remaining}s", False, DIM3)
        surface.blit(timer, ((PHYSICAL_W - timer.get_width()) // 2, 136))

        # ── Instructions ──
        line1 = small_font.render("Confirm this code", False, DIM2)
        line2 = small_font.render("on companion app", False, DIM2)
        surface.blit(line1, ((PHYSICAL_W - line1.get_width()) // 2, 168))
        surface.blit(line2, ((PHYSICAL_W - line2.get_width()) // 2, 180))

        # ── Key hint bar ──
        hint = hint_font.render("LONG:CANCEL", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 2))

    def _render_result(self, surface, body_font, small_font, message, color):
        text = body_font.render(message, False, color)
        surface.blit(text, ((PHYSICAL_W - text.get_width()) // 2, 120))

    # ── Tick / Update ─────────────────────────────────────────────

    def tick(self, dt_ms: int) -> bool:
        """Called by ScreenManager.update(). Returns False when overlay should be dismissed."""
        dt = max(0, dt_ms) / 1000.0
        self._elapsed += dt
        self._blink_timer += dt
        if self._blink_timer >= 0.5:
            self._blink = not self._blink
            self._blink_timer = 0.0
        if self._state == "showing" and self._elapsed >= self._timeout_s:
            self._state = "timeout"
            if self._on_timeout:
                self._on_timeout()
            return False
        return self._state == "showing"

    # ── Input ─────────────────────────────────────────────────────

    def handle_input(self, action: str) -> bool:
        """Only LONG_PRESS cancels. Everything else is consumed (blocked)."""
        if action == "LONG_PRESS" and self._state == "showing":
            self._state = "failed"
            if self._on_cancelled:
                self._on_cancelled()
            return True
        return True  # consume all input while overlay is active

    # ── BLE agent callbacks ───────────────────────────────────────

    def confirm(self) -> None:
        """Called by BLE pairing agent when phone confirms."""
        self._state = "confirmed"
        if self._on_confirmed:
            self._on_confirmed()

    def reject(self) -> None:
        """Called by BLE pairing agent on mismatch/failure."""
        self._state = "failed"

    # ── Properties ────────────────────────────────────────────────

    @property
    def is_active(self) -> bool:
        return self._state == "showing"

    @property
    def state(self) -> str:
        return self._state

    @property
    def passkey(self) -> str:
        return self._passkey

    # ── Font cache ────────────────────────────────────────────────

    def _font(self, key: str) -> pygame.font.Font:
        if key in self._fonts:
            return self._fonts[key]
        try:
            font = pygame.font.Font(FONT_PATH, FONT_SIZES[key])
        except FileNotFoundError:
            font = pygame.font.SysFont("monospace", FONT_SIZES[key])
        self._fonts[key] = font
        return font
