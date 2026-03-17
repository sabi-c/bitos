"""Interactive notification banner — wakes screen and captures gestures.

Two render modes:
- **Compact** (screen awake): top strip with progress bar, same as NotificationToast
- **Full banner** (screen was dark): centered card with message + gesture hints

Gestures (override all screens while banner is active):
- SHORT_PRESS: start recording a voice reply
- HOLD_START/HOLD_END: quick-talk reply
- DOUBLE_PRESS: dismiss banner, return to normal screen

The banner is pushed onto the ScreenManager's notification slot.
When the user responds (record or quick-talk), the banner passes the
reply text back via on_reply callback, then dismisses.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Literal

import pygame

from display.tokens import (
    BLACK, WHITE, DIM1, DIM2, DIM3, HAIRLINE,
    PHYSICAL_W, PHYSICAL_H, SAFE_INSET, STATUS_BAR_H,
    FONT_PATH, FONT_SIZES,
)

# ── Animation & category constants ───────────────────────────────────

ENTRANCE_MS = 200
EXIT_MS = 150
BANNER_H = 72
PROGRESS_BAR_H = 2

CATEGORY_COLORS: dict[str, tuple[int, int, int]] = {
    "sms": (60, 130, 220),
    "mail": (180, 140, 60),
    "calendar": (80, 180, 120),
    "task": (160, 100, 220),
    "agent": (100, 200, 200),
    "reminder": (220, 80, 80),
    "tool": (100, 200, 200),
    "system": (120, 120, 120),
}


def _ease_out_cubic(t: float) -> float:
    """Ease-out cubic: decelerating curve (0→1)."""
    t = max(0.0, min(1.0, t))
    return 1.0 - (1.0 - t) ** 3


@dataclass
class NotificationBanner:
    """Interactive notification that captures all gestures until dismissed."""

    app: str
    icon: str
    message: str
    time_str: str
    was_sleeping: bool = False
    duration_ms: int = 15000  # longer than toast — waits for interaction
    on_dismiss: Callable[[], None] | None = None
    on_reply: Callable[[str], None] | None = None  # called with "record" or "quick_talk"
    elapsed_ms: int = 0
    category: str = "system"
    _dismissed: bool = field(default=False, init=False)
    _fonts: dict[str, pygame.font.Font] = field(default_factory=dict, init=False, repr=False)

    @property
    def dismissed(self) -> bool:
        return self._dismissed

    @property
    def progress(self) -> float:
        """Remaining time fraction: 1.0 → 0.0 over duration."""
        return max(0.0, 1.0 - self.elapsed_ms / max(1, self.duration_ms))

    @property
    def category_color(self) -> tuple[int, int, int]:
        """RGB colour for the current category."""
        return CATEGORY_COLORS.get(self.category, CATEGORY_COLORS["system"])

    @property
    def slide_y_offset(self) -> float:
        """Vertical offset for entrance/exit slide animation.

        Entrance (0→ENTRANCE_MS): ease-out-cubic from -BANNER_H to 0
        with a 2px overshoot bounce.
        Exit (last EXIT_MS): slide up and fade out.
        Middle: 0 (fully visible).
        """
        # Exit phase — last EXIT_MS of duration
        remaining_ms = self.duration_ms - self.elapsed_ms
        if remaining_ms <= EXIT_MS and self.elapsed_ms > ENTRANCE_MS:
            t = 1.0 - (remaining_ms / max(1, EXIT_MS))  # 0→1 as we exit
            return -BANNER_H * _ease_out_cubic(t)

        # Entrance phase — first ENTRANCE_MS
        if self.elapsed_ms < ENTRANCE_MS:
            t = self.elapsed_ms / ENTRANCE_MS  # 0→1
            eased = _ease_out_cubic(t)
            # Overshoot: go 2px past target then settle
            if eased < 1.0:
                offset = -BANNER_H * (1.0 - eased * 1.028)
            else:
                offset = 0.0
            return offset

        # Settled
        return 0.0

    def tick(self, dt_ms: int) -> bool:
        """Returns True while banner should stay alive."""
        if self._dismissed:
            return False
        self.elapsed_ms += max(0, int(dt_ms))
        if self.elapsed_ms >= self.duration_ms:
            self._dismiss()
            return False
        return True

    def handle_action(self, action: str) -> bool:
        """Intercept all gestures. Returns True if consumed."""
        if self._dismissed:
            return False

        if action == "SHORT_PRESS":
            # Start field recording reply
            if self.on_reply:
                self.on_reply("record")
            self._dismiss()
            return True

        if action == "HOLD_START":
            # Start quick-talk reply
            if self.on_reply:
                self.on_reply("quick_talk")
            self._dismiss()
            return True

        if action == "DOUBLE_PRESS":
            # Dismiss without replying
            self._dismiss()
            return True

        if action == "LONG_PRESS":
            # Also dismiss (consistent with "back" gesture)
            self._dismiss()
            return True

        # Consume all other actions while banner is active
        if action in ("HOLD_END", "TRIPLE_PRESS"):
            return True

        return False

    def render(self, surface: pygame.Surface) -> None:
        """Render banner — full card if was_sleeping, compact strip otherwise."""
        if self._dismissed:
            return

        if self.was_sleeping:
            self._render_full_banner(surface)
        else:
            self._render_compact_strip(surface)

    def _render_compact_strip(self, surface: pygame.Surface) -> None:
        """Top strip toast (same as NotificationToast but with reply hints)."""
        strip_h = 38
        pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, strip_h))

        font = self._font("small")
        hint_font = self._font("hint")

        # App + icon
        left = f"{self.icon} {self.app}"[:14]
        surface.blit(font.render(left, False, BLACK), (4, 3))

        # Time
        surface.blit(font.render(self.time_str[:6], False, BLACK), (PHYSICAL_W - 42, 3))

        # Message
        msg = self.message[:28]
        surface.blit(font.render(msg, False, BLACK), (4, 15))

        # Gesture hints
        hints = "○reply  ◉talk  ◎dismiss"
        surface.blit(hint_font.render(hints, False, DIM3), (4, 28))

        # Progress bar — shrinks left-to-right, colored by category
        progress_w = int(PHYSICAL_W * self.progress)
        pygame.draw.rect(
            surface, self.category_color,
            pygame.Rect(0, strip_h - PROGRESS_BAR_H, progress_w, PROGRESS_BAR_H),
        )

    def _render_full_banner(self, surface: pygame.Surface) -> None:
        """Centered card for when screen was dark — formal notification."""
        surface.fill(BLACK)

        font = self._font("body")
        font_small = self._font("small")
        hint_font = self._font("hint")

        # Card dimensions
        card_w = PHYSICAL_W - SAFE_INSET * 2
        card_h = 140
        card_x = SAFE_INSET
        card_y = (PHYSICAL_H - card_h) // 2

        # Card background (dark gray, subtle border)
        card_rect = pygame.Rect(card_x, card_y, card_w, card_h)
        pygame.draw.rect(surface, (20, 20, 20), card_rect)
        pygame.draw.rect(surface, DIM3, card_rect, 1)

        # App header
        header = f"{self.icon}  {self.app}"
        header_surf = font_small.render(header, False, DIM2)
        surface.blit(header_surf, (card_x + 12, card_y + 12))

        # Time
        time_surf = font_small.render(self.time_str, False, DIM3)
        surface.blit(time_surf, (card_x + card_w - time_surf.get_width() - 12, card_y + 12))

        # Message (word-wrapped, max 3 lines)
        max_msg_w = card_w - 24
        msg_lines = self._wrap_text(self.message, font, max_msg_w)[:3]
        msg_y = card_y + 36
        for line in msg_lines:
            line_surf = font.render(line, False, WHITE)
            surface.blit(line_surf, (card_x + 12, msg_y))
            msg_y += font.get_height() + 4

        # Divider
        div_y = card_y + card_h - 36
        pygame.draw.line(surface, HAIRLINE, (card_x + 12, div_y), (card_x + card_w - 12, div_y))

        # Gesture hints (centered)
        hints = "○reply   ◉talk   ◎dismiss"
        hints_surf = hint_font.render(hints, False, DIM1)
        hints_x = card_x + (card_w - hints_surf.get_width()) // 2
        surface.blit(hints_surf, (hints_x, div_y + 10))

        # Progress bar at bottom of card — shrinks left-to-right, colored by category
        progress_w = int(card_w * self.progress)
        pygame.draw.rect(
            surface, self.category_color,
            pygame.Rect(card_x, card_y + card_h - PROGRESS_BAR_H, progress_w, PROGRESS_BAR_H),
        )

    def _dismiss(self) -> None:
        self._dismissed = True
        if self.on_dismiss:
            self.on_dismiss()

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
        """Simple word-wrap."""
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
