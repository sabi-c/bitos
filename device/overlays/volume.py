"""Volume HUD overlay — brief popup when volume changes, like iPhone."""
from __future__ import annotations

import pygame


# Auto-dismiss after this many milliseconds
DISMISS_MS = 1500

# Overlay box dimensions
BOX_W = 140
BOX_H = 58
BG_COLOR = (20, 20, 20)
BAR_FILLED = (255, 255, 255)
BAR_EMPTY = (60, 60, 60)
TEXT_COLOR = (255, 255, 255)
ICON_COLOR = (255, 255, 255)
MUTE_X_COLOR = (180, 60, 60)


class VolumeOverlay:
    """Non-blocking volume HUD.  Shows speaker icon, percentage, and bar.

    Duck-types with the overlay interface used by ScreenManager:
      tick(dt_ms) -> bool   — False when overlay should be removed
      render(surface, tokens)
      handle_input(action) -> bool  — always False (pass-through)
    """

    def __init__(self, volume_pct: int):
        self._volume = max(0, min(100, int(volume_pct)))
        self._elapsed_ms = 0
        self._fonts: dict[str, pygame.font.Font] = {}

    # ── Public API ───────────────────────────────────────────────

    def update(self, volume_pct: int) -> None:
        """Update displayed volume and reset the dismiss timer."""
        self._volume = max(0, min(100, int(volume_pct)))
        self._elapsed_ms = 0

    def tick(self, dt_ms: int) -> bool:
        """Returns True while the overlay should stay visible."""
        self._elapsed_ms += max(0, int(dt_ms))
        return self._elapsed_ms < DISMISS_MS

    def handle_input(self, action: str) -> bool:
        """Pass-through — never captures input."""
        return False

    def render(self, surface: pygame.Surface, tokens) -> None:
        """Draw the volume HUD centered on screen."""
        sw = tokens.PHYSICAL_W
        sh = tokens.PHYSICAL_H

        box_x = (sw - BOX_W) // 2
        box_y = (sh - BOX_H) // 2

        # Background box
        box_rect = pygame.Rect(box_x, box_y, BOX_W, BOX_H)
        pygame.draw.rect(surface, BG_COLOR, box_rect)
        pygame.draw.rect(surface, (50, 50, 50), box_rect, 1)

        # ── Top row: speaker icon + percentage ────────────────────
        icon_x = box_x + 12
        icon_y = box_y + 10
        self._draw_speaker_icon(surface, icon_x, icon_y, self._volume)

        font = self._font(tokens, "body")
        pct_text = f"{self._volume}%"
        pct_surf = font.render(pct_text, False, TEXT_COLOR)
        pct_x = icon_x + 24
        pct_y = icon_y + (12 - pct_surf.get_height()) // 2
        surface.blit(pct_surf, (pct_x, pct_y))

        # ── Bottom row: progress bar ─────────────────────────────
        bar_x = box_x + 12
        bar_y = box_y + BOX_H - 18
        bar_w = BOX_W - 24
        bar_h = 6

        # Empty bar background
        pygame.draw.rect(surface, BAR_EMPTY, pygame.Rect(bar_x, bar_y, bar_w, bar_h))

        # Filled portion
        filled_w = int(bar_w * self._volume / 100)
        if filled_w > 0:
            pygame.draw.rect(surface, BAR_FILLED, pygame.Rect(bar_x, bar_y, filled_w, bar_h))

    # ── Speaker icon (pixel art with lines/polygons) ─────────────

    def _draw_speaker_icon(self, surface: pygame.Surface, x: int, y: int, volume: int) -> None:
        """Draw a small speaker shape at (x, y).  ~16x12 px."""
        # Speaker body: small rectangle
        body = pygame.Rect(x, y + 3, 5, 6)
        pygame.draw.rect(surface, ICON_COLOR, body)

        # Cone: triangle pointing right
        cone_pts = [(x + 5, y + 1), (x + 11, y - 1), (x + 11, y + 13), (x + 5, y + 11)]
        pygame.draw.polygon(surface, ICON_COLOR, cone_pts)

        if volume == 0:
            # Muted: draw an X
            pygame.draw.line(surface, MUTE_X_COLOR, (x + 13, y + 1), (x + 18, y + 10), 2)
            pygame.draw.line(surface, MUTE_X_COLOR, (x + 18, y + 1), (x + 13, y + 10), 2)
        else:
            # Sound waves (arcs approximated with short lines)
            cx = x + 12
            cy = y + 6
            if volume > 0:
                # First wave (small)
                pygame.draw.arc(surface, ICON_COLOR, pygame.Rect(cx, cy - 4, 6, 8), -0.8, 0.8, 1)
            if volume > 50:
                # Second wave (larger)
                pygame.draw.arc(surface, ICON_COLOR, pygame.Rect(cx + 2, cy - 6, 8, 12), -0.8, 0.8, 1)

    # ── Font cache ───────────────────────────────────────────────

    def _font(self, tokens, key: str) -> pygame.font.Font:
        if key in self._fonts:
            return self._fonts[key]
        try:
            font = pygame.font.Font(tokens.FONT_PATH, tokens.FONT_SIZES[key])
        except (FileNotFoundError, OSError):
            font = pygame.font.SysFont("monospace", tokens.FONT_SIZES.get(key, 14))
        self._fonts[key] = font
        return font


def show_volume_overlay(volume_pct: int, screen_mgr) -> None:
    """Show or update the volume HUD overlay on the screen manager.

    If a VolumeOverlay is already showing, updates it in place (resets timer).
    Otherwise pushes a new one.
    """
    existing = getattr(screen_mgr, "_active_overlay", None)
    if isinstance(existing, VolumeOverlay):
        existing.update(volume_pct)
        return

    overlay = VolumeOverlay(volume_pct)
    screen_mgr.push_overlay(overlay)
