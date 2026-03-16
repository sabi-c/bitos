"""Agent approval overlay — presents options for agent-initiated permission requests.

Shown when the agent calls the `request_approval` tool. Displays a prompt
with 2-3 selectable options. The user cycles through options and confirms.

Gestures:
- TAP (SHORT_PRESS): cycle to next option
- DOUBLE_PRESS: confirm/select the highlighted option
- LONG_PRESS: dismiss/cancel (always returns "cancelled")

Renders as a centered card similar to NotificationBanner full mode.
Duck-types with NotificationBanner so ScreenManager can use it in the
_active_banner slot.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

import pygame

from display.tokens import (
    BLACK, WHITE, DIM1, DIM2, DIM3, HAIRLINE,
    PHYSICAL_W, PHYSICAL_H, SAFE_INSET,
    FONT_PATH, FONT_SIZES,
)


@dataclass
class ApprovalOverlay:
    """Permission request overlay with selectable options."""

    request_id: str
    prompt: str
    options: list[str]
    on_choice: Callable[[str, str], None] | None = None  # (request_id, chosen_option)
    on_cancel: Callable[[str], None] | None = None  # (request_id)
    timeout_ms: int = 60_000  # 60s default timeout
    elapsed_ms: int = 0
    _selected: int = field(default=0, init=False)
    _dismissed: bool = field(default=False, init=False)
    _fonts: dict[str, pygame.font.Font] = field(default_factory=dict, init=False, repr=False)

    @property
    def dismissed(self) -> bool:
        return self._dismissed

    def tick(self, dt_ms: int) -> bool:
        """Returns True while overlay should stay alive."""
        if self._dismissed:
            return False
        self.elapsed_ms += max(0, int(dt_ms))
        if self.elapsed_ms >= self.timeout_ms:
            self._cancel("timeout")
            return False
        return True

    def handle_action(self, action: str) -> bool:
        """Intercept all gestures while active."""
        if self._dismissed:
            return False

        if action == "SHORT_PRESS":
            # Cycle to next option
            self._selected = (self._selected + 1) % len(self.options)
            return True

        if action == "TRIPLE_PRESS":
            # Cycle to previous option
            self._selected = (self._selected - 1) % len(self.options)
            return True

        if action == "DOUBLE_PRESS":
            # Confirm selection
            chosen = self.options[self._selected]
            self._dismissed = True
            if self.on_choice:
                self.on_choice(self.request_id, chosen)
            return True

        if action == "LONG_PRESS":
            # Cancel / dismiss
            self._cancel("dismissed")
            return True

        # Consume all other actions
        if action in ("HOLD_START", "HOLD_END"):
            return True

        return False

    def render(self, surface: pygame.Surface) -> None:
        """Render centered approval card."""
        if self._dismissed:
            return

        # Dim background
        dim = pygame.Surface((PHYSICAL_W, PHYSICAL_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 180))
        surface.blit(dim, (0, 0))

        font = self._font("body")
        font_small = self._font("small")
        hint_font = self._font("hint")

        # Card dimensions — scale with number of options
        option_row_h = max(22, font.get_height() + 8)
        card_w = PHYSICAL_W - SAFE_INSET * 2
        # Header (12) + prompt area (50) + divider (8) + options + divider (8) + hints (20) + progress (4)
        card_h = 12 + 50 + 8 + (option_row_h * len(self.options)) + 8 + 20 + 4
        card_h = min(card_h, PHYSICAL_H - 20)  # cap height
        card_x = SAFE_INSET
        card_y = (PHYSICAL_H - card_h) // 2

        # Card background
        card_rect = pygame.Rect(card_x, card_y, card_w, card_h)
        pygame.draw.rect(surface, (15, 15, 15), card_rect)
        pygame.draw.rect(surface, DIM2, card_rect, 1)

        y = card_y + 10

        # Header
        header_surf = font_small.render("AGENT REQUEST", False, DIM2)
        surface.blit(header_surf, (card_x + 12, y))
        y += header_surf.get_height() + 8

        # Prompt text (word-wrapped, max 3 lines)
        max_msg_w = card_w - 24
        prompt_lines = self._wrap_text(self.prompt, font, max_msg_w)[:3]
        for line in prompt_lines:
            line_surf = font.render(line, False, WHITE)
            surface.blit(line_surf, (card_x + 12, y))
            y += font.get_height() + 3
        y += 6

        # Divider
        pygame.draw.line(surface, HAIRLINE, (card_x + 12, y), (card_x + card_w - 12, y))
        y += 8

        # Options
        for idx, option in enumerate(self.options):
            is_selected = idx == self._selected
            opt_rect = pygame.Rect(card_x + 8, y, card_w - 16, option_row_h)

            if is_selected:
                pygame.draw.rect(surface, WHITE, opt_rect)
                indicator = "> "
                opt_color = BLACK
            else:
                indicator = "  "
                opt_color = DIM1

            opt_text = f"{indicator}{option}"
            opt_surf = font.render(opt_text, False, opt_color)
            opt_y = y + (option_row_h - opt_surf.get_height()) // 2
            surface.blit(opt_surf, (card_x + 12, opt_y))
            y += option_row_h

        y += 4

        # Divider
        pygame.draw.line(surface, HAIRLINE, (card_x + 12, y), (card_x + card_w - 12, y))
        y += 6

        # Gesture hints
        hints = "TAP:next  DBL:select  LONG:cancel"
        hints_surf = hint_font.render(hints, False, DIM3)
        hints_x = card_x + (card_w - hints_surf.get_width()) // 2
        surface.blit(hints_surf, (hints_x, y))

        # Progress bar at bottom of card
        progress_w = int(card_w * min(1.0, self.elapsed_ms / max(1, self.timeout_ms)))
        pygame.draw.rect(surface, DIM3, pygame.Rect(card_x, card_y + card_h - 2, progress_w, 2))

    def _cancel(self, reason: str = "dismissed") -> None:
        self._dismissed = True
        if self.on_cancel:
            self.on_cancel(self.request_id)

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
