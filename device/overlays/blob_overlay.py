"""Voice conversation overlay with animated blob feedback.

Full-screen overlay that handles the complete voice conversation cycle:
  IDLE -> LISTENING -> THINKING -> SPEAKING -> IDLE

The blob provides real-time visual feedback:
  - LISTENING: blob expands and reacts to mic amplitude
  - THINKING: blob contracts with slow rotation
  - SPEAKING: blob pulses with TTS audio amplitude
  - Response text shown as preview at bottom

Gestures while active:
  SHORT_PRESS (IDLE)      -> start recording
  SHORT_PRESS (LISTENING) -> stop recording, send to agent
  SHORT_PRESS (SPEAKING)  -> stop TTS
  SHORT_PRESS (DONE)      -> dismiss
  DOUBLE_PRESS            -> cancel / dismiss
  LONG_PRESS              -> dismiss
  TRIPLE_PRESS            -> dismiss
"""

from __future__ import annotations

import logging
import math
import os
import struct
import threading
import time
import wave
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable

import pygame

from blob.renderer import BlobRendererLite, BlobState
from display.tokens import (
    BLACK, WHITE, DIM1, DIM2, DIM3, HAIRLINE,
    PHYSICAL_W, PHYSICAL_H, SAFE_INSET,
    FONT_PATH, FONT_SIZES,
)

logger = logging.getLogger(__name__)


class VoiceOverlayState(Enum):
    IDLE = auto()
    LISTENING = auto()
    THINKING = auto()
    SPEAKING = auto()
    DONE = auto()


@dataclass
class BlobOverlay:
    """Full-screen voice overlay with animated blob and response preview."""

    audio_pipeline: object  # AudioPipeline
    client: object  # BackendClient
    led: object | None = None
    on_dismiss: Callable[[], None] | None = None
    timeout_ms: int = 15_000  # auto-dismiss after 15s in DONE state

    # Internal state
    _state: VoiceOverlayState = field(default=VoiceOverlayState.IDLE, init=False)
    _dismissed: bool = field(default=False, init=False)
    _elapsed_ms: int = field(default=0, init=False)
    _done_elapsed_ms: int = field(default=0, init=False)
    _transcript: str = field(default="", init=False)
    _response: str = field(default="", init=False)
    _error: str = field(default="", init=False)
    _recording_start: float = field(default=0.0, init=False)
    _voice_stop_event: threading.Event = field(default_factory=threading.Event, init=False)
    _fonts: dict[str, pygame.font.Font] = field(default_factory=dict, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _amplitude: float = field(default=0.0, init=False)
    _blob: BlobRendererLite = field(default=None, init=False)
    _amplitude_thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _amplitude_stop: threading.Event = field(default_factory=threading.Event, init=False)

    def __post_init__(self):
        # Blob centered in top portion of screen
        blob_cy = PHYSICAL_H // 3
        self._blob = BlobRendererLite(cx=PHYSICAL_W // 2, cy=blob_cy, base_radius=36)

    @property
    def dismissed(self) -> bool:
        return self._dismissed

    @property
    def state(self) -> VoiceOverlayState:
        with self._lock:
            return self._state

    def tick(self, dt_ms: int) -> bool:
        """Returns True while overlay should stay alive."""
        if self._dismissed:
            return False
        self._elapsed_ms += max(0, int(dt_ms))

        # Feed amplitude to blob
        with self._lock:
            amp = self._amplitude
        self._blob.set_amplitude(amp)

        # Auto-dismiss in DONE state
        if self._state == VoiceOverlayState.DONE:
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
            if self._state == VoiceOverlayState.IDLE:
                self._start_listening()
                return True
            if self._state == VoiceOverlayState.LISTENING:
                self._stop_listening()
                return True
            if self._state == VoiceOverlayState.SPEAKING:
                self._stop_speaking()
                return True
            if self._state == VoiceOverlayState.DONE:
                self._dismiss()
                return True
            return True  # consume during THINKING

        if action == "DOUBLE_PRESS":
            if self._state == VoiceOverlayState.SPEAKING:
                self._stop_speaking()
                return True
            self._dismiss()
            return True

        if action in ("LONG_PRESS", "TRIPLE_PRESS"):
            self._dismiss()
            return True

        if action in ("HOLD_START", "HOLD_END"):
            return True

        return False

    # ── Voice Pipeline ──────────────────────────────────────────────

    def _start_listening(self):
        """Begin voice capture."""
        if not self.audio_pipeline:
            self._set_error("no mic")
            return

        with self._lock:
            self._state = VoiceOverlayState.LISTENING
            self._recording_start = time.time()
        self._voice_stop_event.clear()
        self._amplitude_stop.clear()
        self._transcript = ""
        self._response = ""
        self._error = ""

        self._blob.set_state(BlobState.LISTENING)

        if self.led:
            self.led.listening()

        # Start recording in background
        threading.Thread(
            target=self._voice_flow, daemon=True, name="blob_overlay_voice",
        ).start()

    def _stop_listening(self):
        """Signal recording to stop and proceed to transcription."""
        self._voice_stop_event.set()

    def _stop_speaking(self):
        """Stop TTS playback."""
        if self.audio_pipeline:
            try:
                self.audio_pipeline.stop_speaking()
            except Exception:
                pass
        with self._lock:
            self._state = VoiceOverlayState.DONE
            self._done_elapsed_ms = 0
        self._blob.set_state(BlobState.IDLE)
        self._amplitude_stop.set()

    def _voice_flow(self):
        """Background thread: record -> transcribe -> chat -> speak -> done."""
        try:
            # Record
            audio_path = self.audio_pipeline.record(max_seconds=15)
            if not audio_path:
                self._set_error("mic init failed")
                return

            # Wait for stop signal (user tap or timeout)
            self._voice_stop_event.wait(timeout=15)
            self.audio_pipeline.stop_recording()

            if self._dismissed:
                return

            # Validate recording
            if not os.path.exists(audio_path) or os.path.getsize(audio_path) <= 44:
                self._set_error("no audio")
                return

            # Transcribe
            with self._lock:
                self._state = VoiceOverlayState.THINKING
            self._blob.set_state(BlobState.THINKING)

            if self.led:
                self.led.thinking()

            text = self.audio_pipeline.transcribe(audio_path).strip()
            if not text:
                self._set_error("no speech")
                return

            with self._lock:
                self._transcript = text

            # Send to agent and stream response
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

            response_text = response_text.strip()
            with self._lock:
                self._response = response_text

            if self._dismissed:
                return

            # Speak the response
            if response_text and self.audio_pipeline:
                with self._lock:
                    self._state = VoiceOverlayState.SPEAKING
                self._blob.set_state(BlobState.SPEAKING)

                if self.led:
                    self.led.speaking()

                # Start amplitude monitoring for speaking state
                self._start_amplitude_monitor()

                try:
                    self.audio_pipeline.speak(response_text)
                except Exception as exc:
                    logger.warning("blob_overlay_speak_failed: %s", exc)
                finally:
                    self._amplitude_stop.set()

            # Done
            with self._lock:
                self._state = VoiceOverlayState.DONE
                self._done_elapsed_ms = 0
            self._blob.set_state(BlobState.IDLE)

            if self.led:
                self.led.off()

        except Exception as exc:
            logger.error("blob_overlay_voice_failed: %s", exc, exc_info=True)
            self._set_error(str(exc)[:24])

    def _start_amplitude_monitor(self):
        """Monitor speaking amplitude for blob animation.

        During SPEAKING state, poll the audio pipeline's player for
        playback activity and simulate amplitude from timing.
        """
        self._amplitude_stop.clear()

        def _monitor():
            while not self._amplitude_stop.is_set():
                if self.audio_pipeline and self.audio_pipeline.is_speaking():
                    # Simulate amplitude with a sine wave while speaking
                    t = time.monotonic()
                    sim_amp = 0.4 + 0.3 * abs(math.sin(t * 4.5))
                    with self._lock:
                        self._amplitude = sim_amp
                else:
                    with self._lock:
                        self._amplitude = 0.0
                self._amplitude_stop.wait(timeout=0.05)

            with self._lock:
                self._amplitude = 0.0

        self._amplitude_thread = threading.Thread(
            target=_monitor, daemon=True, name="blob_amplitude",
        )
        self._amplitude_thread.start()

    def _set_error(self, msg: str):
        """Set error state from any thread."""
        with self._lock:
            self._error = msg
            self._state = VoiceOverlayState.DONE
            self._done_elapsed_ms = 0
        self._blob.set_state(BlobState.IDLE)
        self._amplitude_stop.set()
        if self.led:
            try:
                self.led.error()
            except Exception:
                pass

    def _dismiss(self):
        """Dismiss the overlay and clean up."""
        self._dismissed = True
        self._voice_stop_event.set()
        self._amplitude_stop.set()
        if self.audio_pipeline:
            try:
                self.audio_pipeline.stop_recording()
                if self.audio_pipeline.is_speaking():
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

    # ── Rendering ───────────────────────────────────────────────────

    def render(self, surface: pygame.Surface) -> None:
        """Render the full-screen blob overlay."""
        if self._dismissed:
            return

        with self._lock:
            state = self._state
            transcript = self._transcript
            response = self._response
            error = self._error

        # Full-screen dim background
        dim = pygame.Surface((PHYSICAL_W, PHYSICAL_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 220))
        surface.blit(dim, (0, 0))

        font = self._font("body")
        font_small = self._font("small")
        font_hint = self._font("hint")

        # Draw blob with glow
        self._blob.render_glow(surface, color=WHITE, glow_alpha=20)
        self._blob.render(surface, color=WHITE)

        # State label below blob
        blob_bottom = self._blob.cy + self._blob.base_radius + 24

        state_labels = {
            VoiceOverlayState.IDLE: ("TAP TO SPEAK", DIM2),
            VoiceOverlayState.LISTENING: ("LISTENING", WHITE),
            VoiceOverlayState.THINKING: ("THINKING", DIM1),
            VoiceOverlayState.SPEAKING: ("SPEAKING", DIM1),
            VoiceOverlayState.DONE: ("DONE", DIM2),
        }
        label_text, label_color = state_labels.get(state, ("", DIM2))

        # Animated dots for active states
        if state in (VoiceOverlayState.THINKING,):
            dots = "." * (1 + (self._elapsed_ms // 400) % 3)
            label_text += dots

        label_surf = font_small.render(label_text, False, label_color)
        label_x = (PHYSICAL_W - label_surf.get_width()) // 2
        surface.blit(label_surf, (label_x, blob_bottom))

        # Recording duration
        if state == VoiceOverlayState.LISTENING:
            elapsed = time.time() - self._recording_start
            dur_text = f"{elapsed:.0f}s"
            dur_surf = font_hint.render(dur_text, False, DIM3)
            dur_x = (PHYSICAL_W - dur_surf.get_width()) // 2
            surface.blit(dur_surf, (dur_x, blob_bottom + label_surf.get_height() + 4))

            # Pulsing recording indicator
            pulse = 0.5 + 0.5 * math.sin(self._elapsed_ms / 200.0)
            dot_r = int(3 + pulse * 2)
            dot_color = (255, int(80 * pulse), int(80 * pulse))
            pygame.draw.circle(surface, dot_color, (label_x - 10, blob_bottom + label_surf.get_height() // 2), dot_r)

        # Content area (bottom half)
        content_y = PHYSICAL_H // 2 + 10
        content_x = SAFE_INSET
        max_text_w = PHYSICAL_W - SAFE_INSET * 2

        if state == VoiceOverlayState.DONE and error:
            err_surf = font.render(error, False, (255, 120, 120))
            surface.blit(err_surf, (content_x, content_y))

        elif state in (VoiceOverlayState.THINKING, VoiceOverlayState.SPEAKING, VoiceOverlayState.DONE):
            # Show transcript (dimmed, truncated)
            if transcript:
                trunc_t = transcript[:50] + ("..." if len(transcript) > 50 else "")
                t_lines = self._wrap_text(trunc_t, font_hint, max_text_w)
                y = content_y
                for line in t_lines[:2]:
                    t_surf = font_hint.render(line, False, DIM3)
                    surface.blit(t_surf, (content_x, y))
                    y += font_hint.get_height() + 2

            # Show response (brighter, word-wrapped)
            if response:
                r_y = content_y + (font_hint.get_height() + 2) * min(2, len(transcript.split()) > 0 and 1 or 0) + 8
                lines = self._wrap_text(response, font_hint, max_text_w)
                # Show last N lines that fit (scroll to bottom)
                max_lines = (PHYSICAL_H - r_y - 30) // (font_hint.get_height() + 2)
                max_lines = max(1, max_lines)
                visible = lines[-max_lines:] if len(lines) > max_lines else lines
                for line in visible:
                    line_surf = font_hint.render(line, False, DIM1)
                    surface.blit(line_surf, (content_x, r_y))
                    r_y += font_hint.get_height() + 2

        # Bottom hints
        hint_y = PHYSICAL_H - SAFE_INSET - font_hint.get_height() - 4
        hints = {
            VoiceOverlayState.IDLE: "TAP:speak  DBL:close",
            VoiceOverlayState.LISTENING: "TAP:send  DBL:cancel",
            VoiceOverlayState.THINKING: "DBL:cancel",
            VoiceOverlayState.SPEAKING: "TAP:stop  DBL:close",
            VoiceOverlayState.DONE: "TAP:close",
        }
        hint_text = hints.get(state, "")
        hint_surf = font_hint.render(hint_text, False, DIM3)
        hint_x = (PHYSICAL_W - hint_surf.get_width()) // 2
        surface.blit(hint_surf, (hint_x, hint_y))

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
