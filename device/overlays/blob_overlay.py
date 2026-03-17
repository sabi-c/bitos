"""Blob Agent Overlay — voice-to-agent with animated blob feedback.

Shows a centred blob creature over a dimmed background, cycling through
LISTENING -> THINKING -> RESPONDING -> DONE states. Captures voice via
AudioPipeline, sends to BackendClient, displays truncated response.

Duck-types with NotificationBanner so ScreenManager can host it in the
_active_banner slot.
"""
from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable

import pygame

from display.tokens import (
    BLACK, WHITE, DIM1, DIM2, DIM3, HAIRLINE,
    PHYSICAL_W, PHYSICAL_H, SAFE_INSET,
    FONT_PATH, FONT_SIZES,
)
from blob.renderer import BlobRendererLite

logger = logging.getLogger(__name__)

# Blob display size on screen (upscaled from 64x64)
BLOB_DISPLAY_SIZE = 120


class BlobOverlayState(Enum):
    LISTENING = auto()
    THINKING = auto()
    RESPONDING = auto()
    DONE = auto()


# Map overlay states to blob renderer states
_STATE_MAP = {
    BlobOverlayState.LISTENING: "listening",
    BlobOverlayState.THINKING: "thinking",
    BlobOverlayState.RESPONDING: "speaking",
    BlobOverlayState.DONE: "idle",
}


@dataclass
class BlobOverlay:
    """Voice-to-agent overlay with animated blob rendered on top of any screen."""

    audio_pipeline: object  # AudioPipeline
    client: object  # BackendClient
    led: object | None = None
    on_dismiss: Callable[[], None] | None = None
    timeout_ms: int = 30_000  # auto-dismiss after 30s of inactivity in DONE

    # Internal state
    _state: BlobOverlayState = field(default=BlobOverlayState.LISTENING, init=False)
    _dismissed: bool = field(default=False, init=False)
    _elapsed_ms: int = field(default=0, init=False)
    _done_elapsed_ms: int = field(default=0, init=False)
    _transcript: str = field(default="", init=False)
    _response: str = field(default="", init=False)
    _error: str = field(default="", init=False)
    _recording_start: float = field(default=0.0, init=False)
    _voice_stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _fonts: dict = field(default_factory=dict, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _audio_amplitude: float = field(default=0.0, init=False)

    def __post_init__(self):
        self._renderer = BlobRendererLite(num_blobs=3)
        self._renderer.set_state("listening")
        self._start_recording()

    @property
    def dismissed(self) -> bool:
        return self._dismissed

    def tick(self, dt_ms: int) -> bool:
        """Returns True while overlay should stay alive."""
        if self._dismissed:
            return False
        self._elapsed_ms += max(0, int(dt_ms))
        if self._state == BlobOverlayState.DONE:
            self._done_elapsed_ms += max(0, int(dt_ms))
            if self._done_elapsed_ms >= self.timeout_ms:
                self._dismiss()
                return False
        return True

    def handle_action(self, action: str) -> bool:
        """Intercept all gestures while overlay is active."""
        if self._dismissed:
            return False

        if action == "SHORT_PRESS":
            if self._state == BlobOverlayState.LISTENING:
                self._stop_recording()
                return True
            if self._state == BlobOverlayState.DONE:
                self._dismiss()
                return True
            return True

        if action == "DOUBLE_PRESS":
            if self.audio_pipeline and hasattr(self.audio_pipeline, 'is_speaking'):
                if self.audio_pipeline.is_speaking():
                    self.audio_pipeline.stop_speaking()
                    return True
            self._dismiss()
            return True

        if action in ("LONG_PRESS", "TRIPLE_PRESS"):
            self._dismiss()
            return True

        if action in ("HOLD_START", "HOLD_END"):
            return True

        return False

    def _start_recording(self):
        """Begin voice capture."""
        if not self.audio_pipeline:
            self._error = "no mic"
            self._state = BlobOverlayState.DONE
            self._renderer.set_state("idle")
            return

        self._state = BlobOverlayState.LISTENING
        self._recording_start = time.time()
        self._voice_stop_event.clear()
        self._transcript = ""
        self._response = ""
        self._error = ""

        if self.led:
            self.led.listening()

        threading.Thread(
            target=self._voice_flow, daemon=True, name="blob_overlay_voice",
        ).start()

    def _stop_recording(self):
        """Signal voice capture thread to stop."""
        self._voice_stop_event.set()

    def _voice_flow(self):
        """Background thread: record -> transcribe -> chat -> done."""
        import os

        try:
            audio_path = self.audio_pipeline.record(max_seconds=15)
            if not audio_path:
                self._set_error("mic init failed")
                return

            self._voice_stop_event.wait(timeout=15)
            self.audio_pipeline.stop_recording()

            if self._dismissed:
                return

            if not os.path.exists(audio_path) or os.path.getsize(audio_path) <= 44:
                self._set_error("no audio")
                return

            # Transcribe
            with self._lock:
                self._state = BlobOverlayState.THINKING
                self._renderer.set_state("thinking")
            if self.led:
                self.led.thinking()

            text = self.audio_pipeline.transcribe(audio_path).strip()
            if not text:
                self._set_error("no speech")
                return

            with self._lock:
                self._transcript = text

            # Send to agent
            with self._lock:
                self._state = BlobOverlayState.RESPONDING
                self._renderer.set_state("speaking")
                self._renderer.gestures.trigger("pulse")

            result = self.client.chat(text)
            if isinstance(result, dict) and result.get("error"):
                self._set_error(str(result.get("error", "chat error"))[:30])
                return

            response_text = ""
            for chunk in result:
                if self._dismissed:
                    return
                response_text += chunk
                with self._lock:
                    self._response = response_text

            with self._lock:
                self._response = response_text.strip()
                self._state = BlobOverlayState.DONE
                self._done_elapsed_ms = 0
                self._renderer.set_state("idle")

            if self.led:
                self.led.off()

        except Exception as exc:
            logger.error("blob_overlay_voice_failed: %s", exc, exc_info=True)
            self._set_error(str(exc)[:24])

    def _set_error(self, msg: str):
        """Set error state from any thread."""
        with self._lock:
            self._error = msg
            self._state = BlobOverlayState.DONE
            self._done_elapsed_ms = 0
            self._renderer.set_state("idle")
        if self.led:
            try:
                self.led.error()
            except Exception:
                pass

    def _dismiss(self):
        """Dismiss the overlay."""
        self._dismissed = True
        self._voice_stop_event.set()
        if self.audio_pipeline:
            try:
                self.audio_pipeline.stop_recording()
                if hasattr(self.audio_pipeline, 'is_speaking') and self.audio_pipeline.is_speaking():
                    self.audio_pipeline.stop_speaking()
            except Exception:
                pass
        if self.led:
            try:
                self.led.off()
            except Exception:
                pass
        if self.on_dismiss:
            self.on_dismiss()

    def render(self, surface: pygame.Surface) -> None:
        """Render the blob overlay on top of the current screen."""
        if self._dismissed:
            return

        with self._lock:
            state = self._state
            transcript = self._transcript
            response = self._response
            error = self._error

        # Dim background
        dim = pygame.Surface((PHYSICAL_W, PHYSICAL_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 200))
        surface.blit(dim, (0, 0))

        # Render blob at 64x64 then upscale
        blob_surface = self._renderer.tick(
            dt_ms=max(16, self._elapsed_ms % 100),
            audio_amplitude=self._audio_amplitude,
        )
        blob_scaled = pygame.transform.scale(
            blob_surface, (BLOB_DISPLAY_SIZE, BLOB_DISPLAY_SIZE),
        )
        blob_x = (PHYSICAL_W - BLOB_DISPLAY_SIZE) // 2
        blob_y = 30
        surface.blit(blob_scaled, (blob_x, blob_y))

        # Text area below blob
        font = self._font("body")
        font_small = self._font("small")
        font_hint = self._font("hint")

        text_y = blob_y + BLOB_DISPLAY_SIZE + 10
        inner_x = SAFE_INSET + 4
        max_text_w = PHYSICAL_W - inner_x * 2

        # State label
        state_labels = {
            BlobOverlayState.LISTENING: "LISTENING",
            BlobOverlayState.THINKING: "THINKING",
            BlobOverlayState.RESPONDING: "RESPONDING",
            BlobOverlayState.DONE: "DONE",
        }
        label = state_labels.get(state, "")
        label_color = WHITE if state in (
            BlobOverlayState.LISTENING, BlobOverlayState.RESPONDING,
        ) else DIM2
        label_surf = font_small.render(label, False, label_color)
        label_x = (PHYSICAL_W - label_surf.get_width()) // 2
        surface.blit(label_surf, (label_x, text_y))
        text_y += label_surf.get_height() + 6

        # Divider
        pygame.draw.line(
            surface, HAIRLINE,
            (inner_x, text_y), (PHYSICAL_W - inner_x, text_y),
        )
        text_y += 6

        # Content
        if state == BlobOverlayState.LISTENING:
            elapsed = time.time() - self._recording_start
            # Pulsing dot
            pulse = 0.5 + 0.5 * math.sin(self._elapsed_ms / 200.0)
            dot_r = int(3 + pulse * 2)
            dot_color = (255, int(80 * pulse), int(80 * pulse))
            pygame.draw.circle(surface, dot_color, (inner_x + 5, text_y + 7), dot_r)
            dur_surf = font.render(f" {elapsed:.0f}s", False, WHITE)
            surface.blit(dur_surf, (inner_x + 14, text_y))
            text_y += dur_surf.get_height() + 4
            hint_surf = font_hint.render("TAP to send", False, DIM3)
            surface.blit(hint_surf, (inner_x, text_y))

        elif state == BlobOverlayState.THINKING:
            dots = "." * (1 + (self._elapsed_ms // 400) % 3)
            t_surf = font.render(f"thinking{dots}", False, DIM1)
            surface.blit(t_surf, (inner_x, text_y))

        elif state == BlobOverlayState.RESPONDING:
            if transcript:
                trunc = transcript[:40] + ("..." if len(transcript) > 40 else "")
                t_surf = font_hint.render(trunc, False, DIM3)
                surface.blit(t_surf, (inner_x, text_y))
                text_y += t_surf.get_height() + 4
            dots = "." * (1 + (self._elapsed_ms // 400) % 3)
            wait_surf = font.render(f"streaming{dots}", False, DIM1)
            surface.blit(wait_surf, (inner_x, text_y))

        elif state == BlobOverlayState.DONE:
            if error:
                err_surf = font.render(error, False, (255, 120, 120))
                surface.blit(err_surf, (inner_x, text_y))
            else:
                if transcript:
                    trunc_t = transcript[:36] + ("..." if len(transcript) > 36 else "")
                    t_surf = font_hint.render(trunc_t, False, DIM3)
                    surface.blit(t_surf, (inner_x, text_y))
                    text_y += t_surf.get_height() + 3
                if response:
                    lines = self._wrap_text(response, font, max_text_w)[:3]
                    all_lines = self._wrap_text(response, font, max_text_w)
                    if len(all_lines) > 3:
                        last = lines[-1]
                        if len(last) > 3:
                            lines[-1] = last[:-3] + "..."
                    for line in lines:
                        line_surf = font.render(line, False, WHITE)
                        surface.blit(line_surf, (inner_x, text_y))
                        text_y += font.get_height() + 2

        # Bottom hints
        hint_y = PHYSICAL_H - font_hint.get_height() - 8
        if state == BlobOverlayState.LISTENING:
            hints = "TAP:send  DBL:close"
        elif state == BlobOverlayState.DONE:
            hints = "TAP:close  DBL:close"
        else:
            hints = "DBL:cancel"
        hints_surf = font_hint.render(hints, False, DIM3)
        hints_x = (PHYSICAL_W - hints_surf.get_width()) // 2
        surface.blit(hints_surf, (hints_x, hint_y))

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
