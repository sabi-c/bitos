"""Speaking overlay — bottom strip shown during TTS playback."""
from __future__ import annotations

import pygame


class SpeakingOverlay:
    """Small bottom strip with speaker icon and gesture hints during TTS.

    Gesture handling:
      DOUBLE_PRESS  -> "skip"   (stop current TTS immediately)
      TRIPLE_PRESS  -> "next"   (advance to next page of text)
      HOLD_START    -> "reply"  (stop TTS, start recording)
      SHORT_PRESS   -> "skip"   (also stops TTS for quick tap)
      LONG_PRESS    -> "skip"   (back gesture also stops TTS)
    """

    STRIP_H = 22

    def __init__(self):
        self.active = False
        self._dots = 0
        self._dot_timer_ms = 0
        self._font_cache: dict[int, pygame.font.Font] = {}

    def show(self) -> None:
        self.active = True
        self._dots = 0
        self._dot_timer_ms = 0

    def dismiss(self) -> None:
        self.active = False

    def tick(self, dt_ms: int) -> None:
        if not self.active:
            return
        self._dot_timer_ms += dt_ms
        if self._dot_timer_ms >= 400:
            self._dot_timer_ms = 0
            self._dots = (self._dots + 1) % 4

    def handle_action(self, action: str) -> str | None:
        """Handle gesture while speaking.

        Returns:
          "skip"   — stop TTS playback immediately
          "next"   — advance to next page (TTS may continue or stop)
          "reply"  — stop TTS, start voice recording
          None     — not consumed
        """
        if not self.active:
            return None
        if action in ("SHORT_PRESS", "DOUBLE_PRESS", "LONG_PRESS"):
            return "skip"
        if action == "TRIPLE_PRESS":
            return "next"
        if action == "HOLD_START":
            return "reply"
        return None

    def render(self, surface: pygame.Surface, tokens) -> None:
        if not self.active:
            return
        w = tokens.PHYSICAL_W
        h = tokens.PHYSICAL_H

        y = h - tokens.SAFE_INSET - self.STRIP_H

        # Background strip (dark, semi-transparent feel)
        pygame.draw.rect(surface, tokens.WHITE, pygame.Rect(0, y, w, self.STRIP_H))

        font = self._get_font(tokens, tokens.FONT_SIZES["small"])

        # Speaker icon + "speaking" + dots
        dots_str = "." * self._dots
        text = f"))) speaking{dots_str}"
        text_surf = font.render(text, False, tokens.BLACK)
        surface.blit(text_surf, (8, y + (self.STRIP_H - text_surf.get_height()) // 2))

        # Gesture hints on right
        hint = "dbl:skip  3x:pg"
        hint_surf = font.render(hint, False, tokens.DIM2)
        surface.blit(hint_surf, (w - hint_surf.get_width() - 8, y + (self.STRIP_H - hint_surf.get_height()) // 2))

    def _get_font(self, tokens, size: int) -> pygame.font.Font:
        if size in self._font_cache:
            return self._font_cache[size]
        try:
            font = pygame.font.Font(tokens.FONT_PATH, size)
        except (FileNotFoundError, OSError):
            font = pygame.font.SysFont("monospace", size)
        self._font_cache[size] = font
        return font
