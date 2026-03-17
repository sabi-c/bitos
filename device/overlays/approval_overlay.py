"""Agent approval overlay — presents options for agent-initiated permission requests.

Shown when the agent calls the `request_approval` tool. Displays a prompt
with 2-3 selectable options. The user cycles through options and confirms.

Gestures:
- TAP (SHORT_PRESS): cycle to next option
- DOUBLE_PRESS: confirm/select the highlighted option
- LONG_PRESS: dismiss/cancel (always returns "cancelled")

Renders as a 1-bit UI kit styled card with:
- 3px white outer border
- White header bar with category title in black
- Prompt + description body
- Split buttons at bottom with divider
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

import pygame

from display.tokens import (
    BLACK, WHITE, DIM1, DIM2, DIM3, DIM4, HAIRLINE,
    PHYSICAL_W, PHYSICAL_H, SAFE_INSET,
    FONT_PATH, FONT_SIZES,
)

# ── Category → header label mapping ─────────────────────────────

CATEGORY_HEADERS = {
    "permission": "PERMISSION REQUEST",
    "action": "ACTION REQUIRED",
    "confirm": "CONFIRM",
    "agent": "AGENT REQUEST",
}

OUTER_BORDER = 3
HEADER_H = 26
BUTTON_H = 30
CARD_PAD = 10


@dataclass
class ApprovalOverlay:
    """Permission request overlay with selectable options."""

    request_id: str
    prompt: str
    options: list[str]
    description: str = ""
    category: str = "permission"
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
        """Render 1-bit UI kit styled approval card."""
        if self._dismissed:
            return

        # Dim background
        dim = pygame.Surface((PHYSICAL_W, PHYSICAL_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 180))
        surface.blit(dim, (0, 0))

        font = self._font("body")
        font_small = self._font("small")
        hint_font = self._font("hint")

        # ── Calculate card dimensions ────────────────────────────
        card_w = PHYSICAL_W - SAFE_INSET * 2
        inner_w = card_w - OUTER_BORDER * 2

        # Measure prompt text height
        max_text_w = inner_w - CARD_PAD * 2
        prompt_lines = self._wrap_text(self.prompt, font, max_text_w)[:4]
        prompt_h = len(prompt_lines) * (font.get_height() + 3)

        # Measure description text height
        desc_h = 0
        desc_lines: list[str] = []
        if self.description:
            desc_lines = self._wrap_text(self.description, font_small, max_text_w)[:3]
            desc_h = len(desc_lines) * (font_small.get_height() + 2) + 6

        # Card height: border(3) + header(26) + padding(8) + prompt + desc + padding(8) + buttons + border(3) + progress(3)
        card_h = (
            OUTER_BORDER + HEADER_H
            + CARD_PAD + prompt_h + desc_h + CARD_PAD
            + 1  # divider above buttons
            + BUTTON_H
            + OUTER_BORDER + 3  # progress bar
        )
        card_h = min(card_h, PHYSICAL_H - 20)

        card_x = SAFE_INSET
        card_y = (PHYSICAL_H - card_h) // 2

        # ── Card background + 3px white outer border ────────────
        card_rect = pygame.Rect(card_x, card_y, card_w, card_h)
        pygame.draw.rect(surface, BLACK, card_rect)
        pygame.draw.rect(surface, WHITE, card_rect, OUTER_BORDER)

        # ── White header bar ─────────────────────────────────────
        header_rect = pygame.Rect(
            card_x + OUTER_BORDER,
            card_y + OUTER_BORDER,
            inner_w,
            HEADER_H,
        )
        pygame.draw.rect(surface, WHITE, header_rect)

        header_text = CATEGORY_HEADERS.get(self.category, self.category.upper())
        header_surf = font_small.render(header_text, False, BLACK)
        hx = header_rect.x + (header_rect.width - header_surf.get_width()) // 2
        hy = header_rect.y + (header_rect.height - header_surf.get_height()) // 2
        surface.blit(header_surf, (hx, hy))

        # ── Body: prompt + description ───────────────────────────
        y = card_y + OUTER_BORDER + HEADER_H + CARD_PAD
        body_x = card_x + OUTER_BORDER + CARD_PAD

        for line in prompt_lines:
            line_surf = font.render(line, False, WHITE)
            surface.blit(line_surf, (body_x, y))
            y += font.get_height() + 3

        if desc_lines:
            y += 4
            for line in desc_lines:
                line_surf = font_small.render(line, False, DIM3)
                surface.blit(line_surf, (body_x, y))
                y += font_small.get_height() + 2

        # ── Divider above buttons ────────────────────────────────
        btn_area_y = card_y + card_h - OUTER_BORDER - BUTTON_H - 3
        divider_y = btn_area_y - 1
        pygame.draw.line(
            surface, WHITE,
            (card_x + OUTER_BORDER, divider_y),
            (card_x + card_w - OUTER_BORDER, divider_y),
        )

        # ── Split buttons ────────────────────────────────────────
        n = len(self.options)
        btn_w = inner_w // max(n, 1)

        for idx, option in enumerate(self.options):
            is_selected = idx == self._selected
            bx = card_x + OUTER_BORDER + btn_w * idx
            by = btn_area_y
            bw = btn_w if idx < n - 1 else (inner_w - btn_w * idx)  # last gets remainder

            btn_rect = pygame.Rect(bx, by, bw, BUTTON_H)

            if is_selected:
                pygame.draw.rect(surface, WHITE, btn_rect)
                text_color = BLACK
            else:
                pygame.draw.rect(surface, BLACK, btn_rect)
                text_color = DIM1

            # Button label
            lbl_surf = font_small.render(option, False, text_color)
            lx = bx + (bw - lbl_surf.get_width()) // 2
            ly = by + (BUTTON_H - lbl_surf.get_height()) // 2
            surface.blit(lbl_surf, (lx, ly))

            # Vertical divider between buttons
            if idx < n - 1:
                dx = bx + bw
                pygame.draw.line(
                    surface, WHITE,
                    (dx, btn_area_y),
                    (dx, btn_area_y + BUTTON_H),
                )

        # ── Progress bar at very bottom of card ──────────────────
        progress_w = int(card_w * min(1.0, self.elapsed_ms / max(1, self.timeout_ms)))
        pygame.draw.rect(
            surface, DIM3,
            pygame.Rect(card_x, card_y + card_h - 2, progress_w, 2),
        )

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
