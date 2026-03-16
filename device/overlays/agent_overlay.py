"""Universal Agent Overlay — quick voice-to-agent from ANY screen via triple-click.

Triple-click from anywhere brings up a modal overlay that captures voice,
transcribes it, sends to the agent, and shows a truncated response.

States: IDLE -> RECORDING -> TRANSCRIBING -> RESPONDING -> DONE

Gestures while active:
- SHORT_PRESS (IDLE): start recording
- SHORT_PRESS (RECORDING): stop recording, send to agent
- SHORT_PRESS (DONE): dismiss
- DOUBLE_PRESS: dismiss (or stop TTS if speaking)
- LONG_PRESS: dismiss
- TRIPLE_PRESS: dismiss

Duck-types with NotificationBanner so ScreenManager can host it
in the _active_banner slot.
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

logger = logging.getLogger(__name__)


class AgentOverlayState(Enum):
    IDLE = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    RESPONDING = auto()
    DONE = auto()


@dataclass
class AgentOverlay:
    """Quick voice-to-agent overlay rendered on top of any screen."""

    audio_pipeline: object  # AudioPipeline
    client: object  # BackendClient
    led: object | None = None
    on_dismiss: Callable[[], None] | None = None
    timeout_ms: int = 30_000  # auto-dismiss after 30s of inactivity in DONE

    # Internal state
    _state: AgentOverlayState = field(default=AgentOverlayState.IDLE, init=False)
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

    @property
    def dismissed(self) -> bool:
        return self._dismissed

    def tick(self, dt_ms: int) -> bool:
        """Returns True while overlay should stay alive."""
        if self._dismissed:
            return False
        self._elapsed_ms += max(0, int(dt_ms))
        # Auto-dismiss after timeout in DONE state
        if self._state == AgentOverlayState.DONE:
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
            if self._state == AgentOverlayState.IDLE:
                self._start_recording()
                return True
            if self._state == AgentOverlayState.RECORDING:
                self._stop_recording()
                return True
            if self._state == AgentOverlayState.DONE:
                self._dismiss()
                return True
            # During TRANSCRIBING/RESPONDING, consume but ignore
            return True

        if action == "DOUBLE_PRESS":
            # Stop TTS if speaking, otherwise dismiss
            if self.audio_pipeline and self.audio_pipeline.is_speaking():
                self.audio_pipeline.stop_speaking()
                return True
            self._dismiss()
            return True

        if action in ("LONG_PRESS", "TRIPLE_PRESS"):
            self._dismiss()
            return True

        # Consume all other actions (HOLD_START, HOLD_END)
        if action in ("HOLD_START", "HOLD_END"):
            return True

        return False

    def _start_recording(self):
        """Begin voice capture."""
        if not self.audio_pipeline:
            self._error = "no mic"
            self._state = AgentOverlayState.DONE
            return

        self._state = AgentOverlayState.RECORDING
        self._recording_start = time.time()
        self._voice_stop_event.clear()
        self._transcript = ""
        self._response = ""
        self._error = ""

        if self.led:
            self.led.listening()

        threading.Thread(target=self._voice_flow, daemon=True, name="agent_overlay_voice").start()

    def _stop_recording(self):
        """Signal voice capture thread to stop."""
        self._voice_stop_event.set()

    def _voice_flow(self):
        """Background thread: record -> transcribe -> chat -> done."""
        import os

        try:
            # Record
            audio_path = self.audio_pipeline.record(max_seconds=15)
            if not audio_path:
                self._set_error("mic init failed")
                return

            # Wait for stop signal
            self._voice_stop_event.wait(timeout=15)
            self.audio_pipeline.stop_recording()

            if self._dismissed:
                return

            # Validate
            if not os.path.exists(audio_path) or os.path.getsize(audio_path) <= 44:
                self._set_error("no audio")
                return

            # Transcribe
            with self._lock:
                self._state = AgentOverlayState.TRANSCRIBING
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
                self._state = AgentOverlayState.RESPONDING

            result = self.client.chat(text)
            if isinstance(result, dict) and result.get("error"):
                self._set_error(str(result.get("error", "chat error"))[:30])
                return

            # Stream response
            response_text = ""
            for chunk in result:
                if self._dismissed:
                    return
                response_text += chunk
                with self._lock:
                    self._response = response_text

            with self._lock:
                self._response = response_text.strip()
                self._state = AgentOverlayState.DONE
                self._done_elapsed_ms = 0

            if self.led:
                self.led.off()

        except Exception as exc:
            logger.error("agent_overlay_voice_failed: %s", exc, exc_info=True)
            self._set_error(str(exc)[:24])

    def _set_error(self, msg: str):
        """Set error state from any thread."""
        with self._lock:
            self._error = msg
            self._state = AgentOverlayState.DONE
            self._done_elapsed_ms = 0
        if self.led:
            try:
                self.led.error()
            except Exception:
                pass

    def _dismiss(self):
        """Dismiss the overlay."""
        self._dismissed = True
        # Cancel any ongoing recording
        self._voice_stop_event.set()
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

    def render(self, surface: pygame.Surface) -> None:
        """Render the agent overlay card."""
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

        font = self._font("body")
        font_small = self._font("small")
        font_hint = self._font("hint")

        # Card dimensions
        card_w = PHYSICAL_W - SAFE_INSET * 2
        card_h = 140
        card_x = SAFE_INSET
        card_y = (PHYSICAL_H - card_h) // 2

        # Card background
        card_rect = pygame.Rect(card_x, card_y, card_w, card_h)
        pygame.draw.rect(surface, (10, 10, 10), card_rect)
        pygame.draw.rect(surface, DIM2, card_rect, 1)

        y = card_y + 8
        inner_x = card_x + 10
        max_text_w = card_w - 20

        # Header with state indicator
        header = "AGENT"
        header_surf = font_small.render(header, False, DIM2)
        surface.blit(header_surf, (inner_x, y))

        # State indicator on the right
        state_label = {
            AgentOverlayState.IDLE: "READY",
            AgentOverlayState.RECORDING: "REC",
            AgentOverlayState.TRANSCRIBING: "STT...",
            AgentOverlayState.RESPONDING: "THINKING...",
            AgentOverlayState.DONE: "DONE",
        }.get(state, "")

        state_color = WHITE if state in (AgentOverlayState.RECORDING, AgentOverlayState.RESPONDING) else DIM2
        state_surf = font_small.render(state_label, False, state_color)
        surface.blit(state_surf, (card_x + card_w - 10 - state_surf.get_width(), y))

        y += header_surf.get_height() + 6

        # Divider
        pygame.draw.line(surface, HAIRLINE, (inner_x, y), (card_x + card_w - 10, y))
        y += 6

        # Content area
        if state == AgentOverlayState.IDLE:
            # Prompt to start
            prompt = "TAP to record"
            prompt_surf = font.render(prompt, False, DIM1)
            prompt_y = y + (card_h - (y - card_y) - 30 - prompt_surf.get_height()) // 2
            surface.blit(prompt_surf, (inner_x, prompt_y))

        elif state == AgentOverlayState.RECORDING:
            # Pulsing red dot + duration
            elapsed = time.time() - self._recording_start
            pulse = 0.5 + 0.5 * math.sin(self._elapsed_ms / 200.0)
            dot_r = int(4 + pulse * 2)
            dot_color = (255, int(80 * pulse), int(80 * pulse))
            pygame.draw.circle(surface, dot_color, (inner_x + 6, y + 8), dot_r)

            dur_text = f" {elapsed:.0f}s"
            dur_surf = font.render(dur_text, False, WHITE)
            surface.blit(dur_surf, (inner_x + 16, y))
            y += dur_surf.get_height() + 4

            hint = "TAP to send"
            hint_surf = font_hint.render(hint, False, DIM3)
            surface.blit(hint_surf, (inner_x, y))

        elif state == AgentOverlayState.TRANSCRIBING:
            # Show dots animation
            dots = "." * (1 + (self._elapsed_ms // 400) % 3)
            text_surf = font.render(f"transcribing{dots}", False, DIM1)
            surface.blit(text_surf, (inner_x, y))

        elif state == AgentOverlayState.RESPONDING:
            # Show transcript (truncated) + waiting indicator
            if transcript:
                trunc = transcript[:40] + ("..." if len(transcript) > 40 else "")
                t_surf = font_hint.render(trunc, False, DIM3)
                surface.blit(t_surf, (inner_x, y))
                y += t_surf.get_height() + 4

            dots = "." * (1 + (self._elapsed_ms // 400) % 3)
            wait_surf = font.render(f"thinking{dots}", False, DIM1)
            surface.blit(wait_surf, (inner_x, y))

        elif state == AgentOverlayState.DONE:
            if error:
                err_surf = font.render(error, False, (255, 120, 120))
                surface.blit(err_surf, (inner_x, y))
            else:
                # Show transcript (1 line, dimmed)
                if transcript:
                    trunc_t = transcript[:36] + ("..." if len(transcript) > 36 else "")
                    t_surf = font_hint.render(trunc_t, False, DIM3)
                    surface.blit(t_surf, (inner_x, y))
                    y += t_surf.get_height() + 3

                # Show response (word-wrapped, max 3 lines)
                if response:
                    lines = self._wrap_text(response, font, max_text_w)[:3]
                    if len(self._wrap_text(response, font, max_text_w)) > 3:
                        # Truncate last visible line
                        last = lines[-1]
                        if len(last) > 3:
                            lines[-1] = last[:-3] + "..."
                    for line in lines:
                        line_surf = font.render(line, False, WHITE)
                        surface.blit(line_surf, (inner_x, y))
                        y += font.get_height() + 2

        # Bottom hints
        hint_y = card_y + card_h - font_hint.get_height() - 6
        if state == AgentOverlayState.IDLE:
            hints = "TAP:record  DBL:close"
        elif state == AgentOverlayState.RECORDING:
            hints = "TAP:send  DBL:cancel"
        elif state == AgentOverlayState.DONE:
            hints = "TAP:close  DBL:close"
        else:
            hints = "DBL:cancel"
        hints_surf = font_hint.render(hints, False, DIM3)
        hints_x = card_x + (card_w - hints_surf.get_width()) // 2
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
