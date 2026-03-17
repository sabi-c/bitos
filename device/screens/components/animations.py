"""Task completion animations — checkmark overlay and styled toast.

CheckmarkAnimation: full-screen overlay for task completion (box draw-in, checkmark, label).
ToastAnimation: bottom-anchored toast with success/warning/error styles.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pygame

from display.tokens import (
    BLACK, WHITE, DIM2, DIM3,
    PHYSICAL_W, PHYSICAL_H,
    FONT_PATH, FONT_SIZES,
)

# ── Toast style definitions ──────────────────────────────────────────

TOAST_STYLES: dict[str, dict] = {
    "success": {"color": (0, 204, 102), "icon": "checkmark"},
    "warning": {"color": (255, 204, 0), "icon": "!"},
    "error":   {"color": (244, 68, 68), "icon": "X"},
}

TOAST_H = 40
TOAST_MARGIN = 12
TOAST_ICON_SIZE = 28
TOAST_BORDER = 2
TOAST_DEFAULT_Y = PHYSICAL_H - TOAST_H - TOAST_MARGIN


# ── CheckmarkAnimation ───────────────────────────────────────────────


@dataclass
class CheckmarkAnimation:
    """Full-screen overlay: bordered box draws in, checkmark appears, text fades."""

    text: str = "DONE"
    duration_ms: int = 1200
    elapsed_ms: int = 0
    _fonts: dict[str, pygame.font.Font] = field(default_factory=dict, init=False, repr=False)

    @property
    def finished(self) -> bool:
        return self.elapsed_ms >= self.duration_ms

    @property
    def progress(self) -> float:
        """0.0 → 1.0 over the full duration."""
        return min(1.0, self.elapsed_ms / max(1, self.duration_ms))

    def tick(self, dt_ms: int) -> bool:
        """Advance time. Returns True while animation is alive."""
        if self.finished:
            return False
        self.elapsed_ms += max(0, int(dt_ms))
        return not self.finished

    def render(self, surface: pygame.Surface) -> None:
        """Draw the three-phase animation on *surface*."""
        if self.finished:
            return

        p = self.progress

        # Fade-out alpha in last 20% of animation
        alpha = 255
        if p > 0.8:
            alpha = int(255 * (1.0 - (p - 0.8) / 0.2))

        # Dim background
        dim = pygame.Surface((PHYSICAL_W, PHYSICAL_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, min(180, alpha)))
        surface.blit(dim, (0, 0))

        # Box dimensions
        box_size = 64
        cx = PHYSICAL_W // 2
        cy = PHYSICAL_H // 2 - 10  # slightly above center for text below

        # Phase 1 (0-30%): box draws in
        if p < 0.3:
            phase_t = p / 0.3
            # Draw partial border — perimeter traced clockwise
            self._draw_partial_box(surface, cx, cy, box_size, phase_t, alpha)
        else:
            # Full box
            self._draw_full_box(surface, cx, cy, box_size, alpha)

            # Phase 2 (30-60%): checkmark appears
            if p >= 0.3:
                check_t = min(1.0, (p - 0.3) / 0.3)
                self._draw_checkmark(surface, cx, cy, box_size, check_t, alpha)

            # Phase 3 (60-100%): text label
            if p >= 0.6:
                text_t = min(1.0, (p - 0.6) / 0.15)  # text fades in quickly
                self._draw_label(surface, cx, cy + box_size // 2 + 16, text_t, alpha)

    def _draw_partial_box(
        self, surface: pygame.Surface,
        cx: int, cy: int, size: int, t: float, alpha: int,
    ) -> None:
        """Draw border progressively around the box (clockwise from top-left)."""
        half = size // 2
        x0, y0 = cx - half, cy - half
        x1, y1 = cx + half, cy + half
        perimeter = size * 4
        drawn = int(perimeter * t)

        color = (*WHITE, alpha)
        overlay = pygame.Surface((PHYSICAL_W, PHYSICAL_H), pygame.SRCALPHA)

        # Trace clockwise: top → right → bottom → left
        segments = [
            ((x0, y0), (x1, y0), size),     # top
            ((x1, y0), (x1, y1), size),     # right
            ((x1, y1), (x0, y1), size),     # bottom
            ((x0, y1), (x0, y0), size),     # left
        ]
        remaining = drawn
        for (sx, sy), (ex, ey), seg_len in segments:
            if remaining <= 0:
                break
            frac = min(1.0, remaining / seg_len)
            px = int(sx + (ex - sx) * frac)
            py = int(sy + (ey - sy) * frac)
            pygame.draw.line(overlay, color, (sx, sy), (px, py), 3)
            remaining -= seg_len

        surface.blit(overlay, (0, 0))

    def _draw_full_box(
        self, surface: pygame.Surface,
        cx: int, cy: int, size: int, alpha: int,
    ) -> None:
        half = size // 2
        rect = pygame.Rect(cx - half, cy - half, size, size)
        overlay = pygame.Surface((PHYSICAL_W, PHYSICAL_H), pygame.SRCALPHA)
        pygame.draw.rect(overlay, (*WHITE, alpha), rect, 3)
        surface.blit(overlay, (0, 0))

    def _draw_checkmark(
        self, surface: pygame.Surface,
        cx: int, cy: int, size: int, t: float, alpha: int,
    ) -> None:
        """Draw checkmark inside the box, progressively."""
        overlay = pygame.Surface((PHYSICAL_W, PHYSICAL_H), pygame.SRCALPHA)
        color = (*WHITE, alpha)

        # Checkmark points (relative to box center)
        # Short stroke: top-left to bottom-center
        # Long stroke: bottom-center to top-right
        p1 = (cx - 16, cy - 2)
        p2 = (cx - 4, cy + 14)
        p3 = (cx + 18, cy - 12)

        if t < 0.5:
            # Draw first stroke partially
            frac = t / 0.5
            mid_x = int(p1[0] + (p2[0] - p1[0]) * frac)
            mid_y = int(p1[1] + (p2[1] - p1[1]) * frac)
            pygame.draw.line(overlay, color, p1, (mid_x, mid_y), 3)
        else:
            # Full first stroke + partial second
            pygame.draw.line(overlay, color, p1, p2, 3)
            frac = (t - 0.5) / 0.5
            mid_x = int(p2[0] + (p3[0] - p2[0]) * frac)
            mid_y = int(p2[1] + (p3[1] - p2[1]) * frac)
            pygame.draw.line(overlay, color, p2, (mid_x, mid_y), 3)

        surface.blit(overlay, (0, 0))

    def _draw_label(
        self, surface: pygame.Surface,
        cx: int, y: int, t: float, alpha: int,
    ) -> None:
        font = self._font("small")
        text_alpha = int(alpha * t)
        overlay = pygame.Surface((PHYSICAL_W, PHYSICAL_H), pygame.SRCALPHA)
        text_surf = font.render(self.text, True, (*WHITE, text_alpha))
        text_rect = text_surf.get_rect(center=(cx, y))
        overlay.blit(text_surf, text_rect)
        surface.blit(overlay, (0, 0))

    def _font(self, key: str) -> pygame.font.Font:
        if key in self._fonts:
            return self._fonts[key]
        try:
            font = pygame.font.Font(FONT_PATH, FONT_SIZES[key])
        except FileNotFoundError:
            font = pygame.font.SysFont("monospace", FONT_SIZES[key])
        self._fonts[key] = font
        return font


# ── ToastAnimation ───────────────────────────────────────────────────


@dataclass
class ToastAnimation:
    """Bottom-anchored toast with colored border and icon."""

    text: str = ""
    style: str = "success"
    duration_ms: int = 2000
    elapsed_ms: int = 0
    _fonts: dict[str, pygame.font.Font] = field(default_factory=dict, init=False, repr=False)

    @property
    def finished(self) -> bool:
        return self.elapsed_ms >= self.duration_ms

    @property
    def style_def(self) -> dict:
        return TOAST_STYLES.get(self.style, TOAST_STYLES["success"])

    def tick(self, dt_ms: int) -> bool:
        """Advance time. Returns True while alive."""
        if self.finished:
            return False
        self.elapsed_ms += max(0, int(dt_ms))
        return not self.finished

    def render(self, surface: pygame.Surface, y: int | None = None) -> None:
        """Render the toast bar near the bottom of the screen."""
        if self.finished:
            return

        if y is None:
            y = TOAST_DEFAULT_Y

        style = self.style_def
        border_color = style["color"]
        icon_char = style["icon"]

        # Fade out in last 20%
        alpha = 255
        progress = self.elapsed_ms / max(1, self.duration_ms)
        if progress > 0.8:
            alpha = int(255 * (1.0 - (progress - 0.8) / 0.2))

        toast_w = PHYSICAL_W - TOAST_MARGIN * 2
        x = TOAST_MARGIN

        # Toast background
        overlay = pygame.Surface((toast_w, TOAST_H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, min(230, alpha)))
        surface.blit(overlay, (x, y))

        # Colored border (2px)
        border_rect = pygame.Rect(x, y, toast_w, TOAST_H)
        border_c = (*border_color, alpha) if alpha < 255 else border_color
        # Draw on an alpha surface for fade-out
        if alpha < 255:
            border_surf = pygame.Surface((PHYSICAL_W, PHYSICAL_H), pygame.SRCALPHA)
            pygame.draw.rect(border_surf, (*border_color, alpha), border_rect, TOAST_BORDER)
            surface.blit(border_surf, (0, 0))
        else:
            pygame.draw.rect(surface, border_color, border_rect, TOAST_BORDER)

        # Icon square on left
        icon_x = x + 6
        icon_y = y + (TOAST_H - TOAST_ICON_SIZE) // 2
        icon_rect = pygame.Rect(icon_x, icon_y, TOAST_ICON_SIZE, TOAST_ICON_SIZE)
        if alpha < 255:
            icon_surf = pygame.Surface((PHYSICAL_W, PHYSICAL_H), pygame.SRCALPHA)
            pygame.draw.rect(icon_surf, (*border_color, alpha), icon_rect, 2)
            surface.blit(icon_surf, (0, 0))
        else:
            pygame.draw.rect(surface, border_color, icon_rect, 2)

        font_small = self._font("small")

        # Draw icon character
        if icon_char == "checkmark":
            # Small checkmark inside the icon box
            ic_cx = icon_x + TOAST_ICON_SIZE // 2
            ic_cy = icon_y + TOAST_ICON_SIZE // 2
            p1 = (ic_cx - 7, ic_cy - 1)
            p2 = (ic_cx - 2, ic_cy + 5)
            p3 = (ic_cx + 8, ic_cy - 6)
            if alpha < 255:
                check_surf = pygame.Surface((PHYSICAL_W, PHYSICAL_H), pygame.SRCALPHA)
                pygame.draw.line(check_surf, (*border_color, alpha), p1, p2, 2)
                pygame.draw.line(check_surf, (*border_color, alpha), p2, p3, 2)
                surface.blit(check_surf, (0, 0))
            else:
                pygame.draw.line(surface, border_color, p1, p2, 2)
                pygame.draw.line(surface, border_color, p2, p3, 2)
        else:
            # Text icon (! or X)
            icon_text = font_small.render(icon_char, True, border_color)
            icon_text_rect = icon_text.get_rect(
                center=(icon_x + TOAST_ICON_SIZE // 2, icon_y + TOAST_ICON_SIZE // 2)
            )
            surface.blit(icon_text, icon_text_rect)

        # Toast text
        text_x = icon_x + TOAST_ICON_SIZE + 10
        text_font = self._font("small")
        # Truncate text to fit
        max_text_w = toast_w - (text_x - x) - 8
        display_text = self.text
        while text_font.size(display_text)[0] > max_text_w and len(display_text) > 1:
            display_text = display_text[:-1]

        text_surf = text_font.render(display_text, True, WHITE)
        text_y = y + (TOAST_H - text_surf.get_height()) // 2
        surface.blit(text_surf, (text_x, text_y))

    def _font(self, key: str) -> pygame.font.Font:
        if key in self._fonts:
            return self._fonts[key]
        try:
            font = pygame.font.Font(FONT_PATH, FONT_SIZES[key])
        except FileNotFoundError:
            font = pygame.font.SysFont("monospace", FONT_SIZES[key])
        self._fonts[key] = font
        return font
