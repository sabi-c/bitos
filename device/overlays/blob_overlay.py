"""Voice chat overlay with animated blob — full pipeline.

TRIPLE_PRESS from any screen opens this overlay. Flow:

1. Overlay opens -> SharedAudioStream starts -> VoiceRecorder begins
2. Blob animates LISTENING state, pulses with mic amplitude
3. VAD detects 2s silence (or user DOUBLE_PRESS to force-send)
4. Blob transitions to THINKING while STT + /chat runs
5. Response streams in -> TTS plays -> Blob SPEAKING with audio amplitude
6. Response text shown below blob
7. Auto-dismiss 2s after TTS completes

Gestures:
  SHORT_PRESS  during RECORDING -> cancel
  DOUBLE_PRESS during RECORDING -> force send now
  SHORT_PRESS  during DONE      -> dismiss
  LONG_PRESS   anytime          -> dismiss
  TRIPLE_PRESS anytime          -> dismiss (toggle off)
"""

from __future__ import annotations

import io
import logging
import math
import os
import tempfile
import threading
import time
import wave
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Callable

import numpy as np
import pygame

from display.tokens import (
    BLACK,
    WHITE,
    DIM1,
    DIM2,
    DIM3,
    HAIRLINE,
    PHYSICAL_W,
    PHYSICAL_H,
    SAFE_INSET,
    FONT_PATH,
    FONT_SIZES,
)

logger = logging.getLogger(__name__)


class BlobOverlayState(Enum):
    LISTENING = auto()
    THINKING = auto()
    SPEAKING = auto()
    DONE = auto()


@dataclass
class BlobOverlay:
    """Full voice-to-agent overlay with animated blob and TTS response."""

    client: object  # BackendClient
    audio_pipeline: object  # AudioPipeline (for TTS speak/stop)
    shared_stream: object | None = None  # SharedAudioStream (for mic)
    led: object | None = None
    on_dismiss: Callable[[], None] | None = None
    auto_dismiss_ms: int = 3000  # dismiss 3s after DONE

    # Internal
    _state: BlobOverlayState = field(default=BlobOverlayState.LISTENING, init=False)
    _dismissed: bool = field(default=False, init=False)
    _amplitude: float = field(default=0.0, init=False)
    _transcript: str = field(default="", init=False)
    _response: str = field(default="", init=False)
    _error: str = field(default="", init=False)
    _elapsed_ms: int = field(default=0, init=False)
    _done_elapsed_ms: int = field(default=0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)
    _recorder: object = field(default=None, init=False, repr=False)
    _blob: object = field(default=None, init=False, repr=False)
    _fonts: dict = field(default_factory=dict, init=False, repr=False)
    _tts_thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _stream_started: bool = field(default=False, init=False)

    def __post_init__(self):
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
            if self._done_elapsed_ms >= self.auto_dismiss_ms:
                self._dismiss()
                return False

        return True

    def handle_action(self, action: str) -> bool:
        """Intercept button gestures while overlay is active."""
        if self._dismissed:
            return False

        if action == "SHORT_PRESS":
            if self._state == BlobOverlayState.LISTENING:
                # Cancel recording
                self._cancel_recording()
                self._dismiss()
                return True
            if self._state == BlobOverlayState.DONE:
                self._dismiss()
                return True
            return True  # consume during THINKING/SPEAKING

        if action == "DOUBLE_PRESS":
            if self._state == BlobOverlayState.LISTENING:
                # Force send now
                self._force_send()
                return True
            if self._state == BlobOverlayState.SPEAKING:
                # Stop TTS
                self._stop_tts()
                return True
            self._dismiss()
            return True

        if action in ("LONG_PRESS", "TRIPLE_PRESS"):
            self._dismiss()
            return True

        if action in ("HOLD_START", "HOLD_END"):
            return True

        return False

    def render(self, surface: pygame.Surface) -> None:
        """Render blob overlay on top of current screen."""
        if self._dismissed:
            return

        with self._lock:
            state = self._state
            amplitude = self._amplitude
            transcript = self._transcript
            response = self._response
            error = self._error

        # Full screen dim background
        dim = pygame.Surface((PHYSICAL_W, PHYSICAL_H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 220))
        surface.blit(dim, (0, 0))

        # Render blob centered in upper portion
        blob_cx = PHYSICAL_W // 2
        blob_cy = 80
        self._render_blob(surface, blob_cx, blob_cy, state, amplitude)

        # State label below blob
        font_small = self._font("small")
        font_body = self._font("body")
        font_hint = self._font("hint")

        label_y = blob_cy + 50

        state_labels = {
            BlobOverlayState.LISTENING: "LISTENING",
            BlobOverlayState.THINKING: "THINKING",
            BlobOverlayState.SPEAKING: "SPEAKING",
            BlobOverlayState.DONE: "DONE" if not error else "ERROR",
        }
        label = state_labels.get(state, "")

        # Animate dots for active states
        if state in (BlobOverlayState.LISTENING, BlobOverlayState.THINKING):
            dots = "." * (1 + (self._elapsed_ms // 400) % 3)
            label += dots

        label_color = WHITE if state in (BlobOverlayState.LISTENING, BlobOverlayState.SPEAKING) else DIM2
        label_surf = font_small.render(label, False, label_color)
        label_x = (PHYSICAL_W - label_surf.get_width()) // 2
        surface.blit(label_surf, (label_x, label_y))

        # Content area
        content_y = label_y + label_surf.get_height() + 10
        inner_x = SAFE_INSET + 4
        max_w = PHYSICAL_W - (SAFE_INSET + 4) * 2

        if state == BlobOverlayState.LISTENING:
            # Show recording duration
            dur = self._elapsed_ms / 1000.0
            dur_text = f"{dur:.0f}s"
            dur_surf = font_body.render(dur_text, False, DIM2)
            dur_x = (PHYSICAL_W - dur_surf.get_width()) // 2
            surface.blit(dur_surf, (dur_x, content_y))

        elif state == BlobOverlayState.THINKING:
            # Show transcript
            if transcript:
                trunc = transcript[:50] + ("..." if len(transcript) > 50 else "")
                t_surf = font_hint.render(trunc, False, DIM3)
                surface.blit(t_surf, (inner_x, content_y))

        elif state == BlobOverlayState.SPEAKING:
            # Show response text streaming in (max 4 lines)
            if response:
                lines = self._wrap_text(response, font_hint, max_w)[:4]
                for i, line in enumerate(lines):
                    line_surf = font_hint.render(line, False, DIM1)
                    surface.blit(line_surf, (inner_x, content_y + i * (font_hint.get_height() + 2)))

        elif state == BlobOverlayState.DONE:
            if error:
                err_surf = font_body.render(error, False, (255, 120, 120))
                surface.blit(err_surf, (inner_x, content_y))
            else:
                # Show truncated response
                if response:
                    lines = self._wrap_text(response, font_hint, max_w)[:5]
                    for i, line in enumerate(lines):
                        line_surf = font_hint.render(line, False, WHITE if i == 0 else DIM1)
                        surface.blit(line_surf, (inner_x, content_y + i * (font_hint.get_height() + 2)))

        # Bottom hints
        hint_y = PHYSICAL_H - SAFE_INSET - font_hint.get_height() - 4
        hints = {
            BlobOverlayState.LISTENING: "tap:cancel  dbl:send",
            BlobOverlayState.THINKING: "hold:cancel",
            BlobOverlayState.SPEAKING: "dbl:skip",
            BlobOverlayState.DONE: "tap:close",
        }.get(state, "")
        if hints:
            hints_surf = font_hint.render(hints, False, DIM3)
            hints_x = (PHYSICAL_W - hints_surf.get_width()) // 2
            surface.blit(hints_surf, (hints_x, hint_y))

    # ── Blob rendering ──

    def _render_blob(
        self,
        surface: pygame.Surface,
        cx: int,
        cy: int,
        state: BlobOverlayState,
        amplitude: float,
    ) -> None:
        """Draw animated blob at (cx, cy)."""
        t = self._elapsed_ms / 1000.0

        # State-dependent animation
        if state == BlobOverlayState.LISTENING:
            react = 0.15 * amplitude
            breath = 1.12 + 0.04 * math.sin(t * 2.5) + react
            wobble = 0.08 + 0.12 * amplitude
            rot_speed = 0.6 + amplitude * 0.8
            color = WHITE
        elif state == BlobOverlayState.THINKING:
            breath = 0.88 + 0.10 * math.sin(t * 1.2)
            wobble = 0.04
            rot_speed = 1.5
            color = DIM2
        elif state == BlobOverlayState.SPEAKING:
            react = 0.18 * amplitude
            breath = 1.0 + 0.05 * math.sin(t * 3.0) + react
            wobble = 0.06 + 0.1 * amplitude
            rot_speed = 0.8
            color = WHITE
        else:  # DONE
            breath = 1.0 + 0.04 * math.sin(t * 1.5)
            wobble = 0.02
            rot_speed = 0.2
            color = DIM1

        base_r = 28 * breath

        # Sub-blob definitions: (angle, dist_factor, radius_factor)
        blobs = [
            (0.0, 0.0, 1.0),
            (0.0, 0.45, 0.55),
            (math.pi * 0.5, 0.45, 0.55),
            (math.pi, 0.45, 0.55),
            (math.pi * 1.5, 0.45, 0.55),
            (math.pi * 0.25, 0.35, 0.4),
            (math.pi * 0.75, 0.35, 0.4),
            (math.pi * 1.25, 0.35, 0.4),
            (math.pi * 1.75, 0.35, 0.4),
        ]

        # Glow effect
        glow_r = int(base_r * 1.6)
        if glow_r > 2:
            glow_surf = pygame.Surface((glow_r * 2, glow_r * 2), pygame.SRCALPHA)
            for ring in range(3):
                r = glow_r - ring * (glow_r // 4)
                alpha = max(5, 25 - ring * 8)
                pygame.draw.circle(glow_surf, (*color, alpha), (glow_r, glow_r), max(1, r))
            surface.blit(glow_surf, (cx - glow_r, cy - glow_r))

        # Draw sub-blobs
        for i, (angle, dist_f, r_f) in enumerate(blobs):
            a = angle + t * rot_speed + wobble * math.sin(t * 3.7 + i * 1.3)
            dist = base_r * dist_f
            r = max(1, int(base_r * r_f))
            bx = int(cx + dist * math.cos(a))
            by = int(cy + dist * math.sin(a))
            c = color if i == 0 else tuple(max(0, min(255, int(v * 0.85))) for v in color)
            pygame.draw.circle(surface, c, (bx, by), r)

    # ── Voice pipeline ──

    def _start_recording(self) -> None:
        """Begin voice capture via SharedAudioStream + VoiceRecorder."""
        if not self.shared_stream:
            # Fallback: use audio_pipeline directly (legacy path)
            self._start_recording_legacy()
            return

        from audio.voice_recorder import VoiceRecorder

        def on_amplitude(amp: float):
            with self._lock:
                self._amplitude = amp

        def on_done(wav_bytes: bytes | None):
            if self._dismissed:
                return
            if wav_bytes is None:
                self._set_error("no speech")
                return
            # Save WAV to temp file for STT
            threading.Thread(
                target=self._process_audio,
                args=(wav_bytes,),
                daemon=True,
                name="blob_overlay_process",
            ).start()

        self._recorder = VoiceRecorder(
            shared_stream=self.shared_stream,
            on_amplitude=on_amplitude,
            on_done=on_done,
            silence_timeout=2.0,
            max_duration=30.0,
        )

        if self.led:
            self.led.listening()

        if not self._recorder.start():
            self._set_error("mic unavailable")

    def _start_recording_legacy(self) -> None:
        """Fallback: use AudioPipeline.record() directly."""
        if not self.audio_pipeline:
            self._set_error("no audio")
            return

        if self.led:
            self.led.listening()

        threading.Thread(
            target=self._legacy_voice_flow,
            daemon=True,
            name="blob_overlay_legacy",
        ).start()

    def _legacy_voice_flow(self) -> None:
        """Legacy path using AudioPipeline for recording."""
        try:
            audio_path = self.audio_pipeline.record(max_seconds=30)
            if not audio_path:
                self._set_error("mic failed")
                return

            # Wait for force_send or timeout
            # The user presses DOUBLE to force-send, which calls _force_send()
            # For legacy path, we just wait a bit then stop
            time.sleep(0.5)
            while not self._dismissed and self._state == BlobOverlayState.LISTENING:
                time.sleep(0.1)
                if self._elapsed_ms > 30000:
                    break

            self.audio_pipeline.stop_recording()

            if self._dismissed:
                return

            if not os.path.exists(audio_path) or os.path.getsize(audio_path) <= 44:
                self._set_error("no audio")
                return

            # Read WAV bytes
            with open(audio_path, "rb") as f:
                wav_bytes = f.read()

            try:
                os.unlink(audio_path)
            except OSError:
                pass

            self._process_audio(wav_bytes)

        except Exception as exc:
            logger.error("blob_overlay_legacy_failed: %s", exc, exc_info=True)
            self._set_error(str(exc)[:24])

    def _force_send(self) -> None:
        """Force-finish recording immediately."""
        if self._recorder:
            self._recorder.force_send()
        elif self.audio_pipeline:
            # Legacy: stop recording
            try:
                self.audio_pipeline.stop_recording()
            except Exception:
                pass

    def _cancel_recording(self) -> None:
        """Cancel recording without sending."""
        if self._recorder:
            self._recorder.stop()
        elif self.audio_pipeline:
            try:
                self.audio_pipeline.stop_recording()
            except Exception:
                pass

    def _process_audio(self, wav_bytes: bytes) -> None:
        """Transcribe audio, send to agent, play TTS response."""
        # Transition to THINKING
        with self._lock:
            self._state = BlobOverlayState.THINKING
            self._amplitude = 0.0

        if self.led:
            try:
                self.led.thinking()
            except Exception:
                pass

        try:
            # Write WAV to temp file for STT
            fd, tmp_path = tempfile.mkstemp(prefix="bitos_blob_", suffix=".wav")
            os.close(fd)
            with open(tmp_path, "wb") as f:
                f.write(wav_bytes)

            # Transcribe
            transcript = ""
            try:
                transcript = self.audio_pipeline.transcribe(tmp_path).strip()
            except Exception as exc:
                logger.error("blob_overlay_transcribe_failed: %s", exc)
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

            if not transcript:
                self._set_error("no speech")
                return

            with self._lock:
                self._transcript = transcript

            if self._dismissed:
                return

            # Send to agent (streaming)
            result = self.client.chat(transcript)
            if isinstance(result, dict) and result.get("error"):
                self._set_error(str(result.get("error", "chat error"))[:30])
                return

            # Stream response chunks
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

            if not response_text:
                self._set_done()
                return

            # TTS playback
            self._play_tts(response_text)

        except Exception as exc:
            logger.error("blob_overlay_process_failed: %s", exc, exc_info=True)
            self._set_error(str(exc)[:24])

    def _play_tts(self, text: str) -> None:
        """Play TTS response with SPEAKING blob animation."""
        with self._lock:
            self._state = BlobOverlayState.SPEAKING

        if self.led:
            try:
                self.led.speaking()
            except Exception:
                pass

        try:
            if self.audio_pipeline:
                self.audio_pipeline.speak(text)
        except Exception as exc:
            logger.warning("blob_overlay_tts_failed: %s", exc)

        self._set_done()

    def _stop_tts(self) -> None:
        """Stop TTS playback immediately."""
        if self.audio_pipeline:
            try:
                self.audio_pipeline.stop_speaking()
            except Exception:
                pass
        self._set_done()

    def _set_done(self) -> None:
        """Transition to DONE state."""
        with self._lock:
            self._state = BlobOverlayState.DONE
            self._done_elapsed_ms = 0
            self._amplitude = 0.0
        if self.led:
            try:
                self.led.off()
            except Exception:
                pass

    def _set_error(self, msg: str) -> None:
        """Set error and transition to DONE."""
        with self._lock:
            self._error = msg
            self._state = BlobOverlayState.DONE
            self._done_elapsed_ms = 0
            self._amplitude = 0.0
        if self.led:
            try:
                self.led.error()
            except Exception:
                pass

    def _dismiss(self) -> None:
        """Dismiss overlay, cleanup all resources."""
        self._dismissed = True

        # Cancel any recording
        self._cancel_recording()

        # Stop any TTS
        if self.audio_pipeline:
            try:
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

    # ── Helpers ──

    def _font(self, key: str) -> pygame.font.Font:
        if key in self._fonts:
            return self._fonts[key]
        try:
            font = pygame.font.Font(FONT_PATH, FONT_SIZES[key])
        except (FileNotFoundError, OSError):
            font = pygame.font.SysFont("monospace", FONT_SIZES.get(key, 10))
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
