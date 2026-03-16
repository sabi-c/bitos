"""Quick capture overlay for always-available note capture."""
from __future__ import annotations

import logging
import threading
import time

import pygame

from display.tokens import BLACK, WHITE, DIM2, DIM3, PHYSICAL_W, PHYSICAL_H, STATUS_BAR_H, FONT_PATH, FONT_SIZES

logger = logging.getLogger(__name__)


class QuickCaptureOverlay:
    def __init__(self, repository, audio_pipeline=None, context: str = "", on_saved=None, on_dismiss=None):
        self._repository = repository
        self._audio_pipeline = audio_pipeline
        self._context = context
        self._on_saved = on_saved
        self._on_dismiss = on_dismiss
        self._fonts: dict[str, pygame.font.Font] = {}
        self._text = ""
        self._mode = "voice" if audio_pipeline else "keyboard"
        self._saved_until: float | None = None
        self._capture_number = self._repository.get_capture_count() + 1

    def render(self, surface, tokens=None) -> None:
        surface.fill(BLACK)
        self._draw_line(surface, "QUICK CAPTURE", 4, y=4)
        self._draw_line(surface, f"CAPTURE #{self._capture_number}", 4, y=STATUS_BAR_H + 8, small=True)

        if self._mode == "voice":
            prompt = "HOLD TO SPEAK"
            self._draw_line(surface, prompt, 8, y=STATUS_BAR_H + 36)
            self._draw_line(surface, self._text[-36:] or "(no speech yet)", 8, y=STATUS_BAR_H + 58, dim=True)
        else:
            self._draw_line(surface, "TYPE YOUR CAPTURE", 8, y=STATUS_BAR_H + 36)
            shown = self._text[-42:]
            self._draw_line(surface, shown or "_", 8, y=STATUS_BAR_H + 58)

        if self._saved_until and time.time() < self._saved_until:
            self._draw_line(surface, "CAPTURED ✓", 8, y=PHYSICAL_H - 34)

        self._draw_line(surface, "DBL:SAVE · LONG:CANCEL · TAB:MODE", 4, y=PHYSICAL_H - 16, small=True, dim=True)

    def _draw_line(self, surface, text: str, x: int, y: int, small: bool = False, dim: bool = False):
        key = "small" if small else "body"
        font = self._font(key)
        color = DIM3 if dim else (DIM2 if small else WHITE)
        surface.blit(font.render(text, False, color), (x, y))

    def _font(self, key: str) -> pygame.font.Font:
        if key in self._fonts:
            return self._fonts[key]
        try:
            font = pygame.font.Font(FONT_PATH, FONT_SIZES[key])
        except FileNotFoundError:
            font = pygame.font.SysFont("monospace", FONT_SIZES[key])
        self._fonts[key] = font
        return font

    def tick(self, dt_ms: int) -> bool:
        _ = dt_ms
        if self._saved_until and time.time() >= self._saved_until:
            if self._on_dismiss:
                self._on_dismiss()
            return False
        return True

    def handle_input(self, action: str) -> bool:
        # VERIFIED: LONG cancels; DBL saves and then toast is shown by runtime callback.
        if action == "LONG_PRESS":
            if self._on_dismiss:
                self._on_dismiss()
            return False
        if action == "TRIPLE_PRESS":
            self._mode = "keyboard" if self._mode == "voice" else "voice"
            return True
        if action == "DOUBLE_PRESS":
            self._confirm_and_save()
            return True
        return True

    def handle_keyboard_input(self, event: pygame.event.Event) -> bool:
        if event.type != pygame.KEYDOWN:
            return False
        if event.key == pygame.K_TAB:
            self._mode = "keyboard" if self._mode == "voice" else "voice"
            return True
        if self._mode != "keyboard":
            return False
        if event.key == pygame.K_BACKSPACE:
            self._text = self._text[:-1]
            return True
        if event.unicode and event.unicode.isprintable():
            self._text += event.unicode
            return True
        return False

    def _confirm_and_save(self):
        if self._mode == "voice" and self._audio_pipeline and not self._text.strip():
            self._capture_voice()
        if not self._text.strip():
            self._text = "(empty capture)"
        capture_id = self._repository.save_quick_capture(self._text.strip(), context=self._context)
        if self._on_saved:
            self._on_saved(capture_id, self._text.strip())
        self._saved_until = time.time() + 1.5

    def _capture_voice(self):
        try:
            audio_path = self._audio_pipeline.record(max_seconds=8)
            if audio_path:
                text = self._audio_pipeline.transcribe(audio_path).strip()
                if text:
                    self._text = text
        except Exception as exc:
            logger.warning("quick_capture_voice_failed error=%s", exc)
