"""ChatPreviewPanel — ambient greeting + voice-first response field.

Top area: dynamic-height typewriter greeting from agent.
First submenu item: RECORD — inline recording with state machine
  (READY → RECORDING → TRANSCRIBING → LAUNCHING → handoff to ChatPanel).
Below: START NEW CHAT, RESUME CHAT, CHAT HISTORY, SETTINGS, BACK TO MAIN MENU.
"""

from __future__ import annotations

import math
import threading
import time
from enum import Enum, auto

import pygame

from device.display.theme import get_font
from device.display.tokens import DIM2, DIM3, HAIRLINE, WHITE
from device.display.animator import blink_cursor
from device.display.typewriter import TypewriterRenderer
from device.ui.panels.base import PreviewPanel, ITEM_H, PAD_X, PAD_Y, FONT_SIZE


# ── Greeting area constants ──
GREETING_H_MIN = 40
GREETING_H_DEFAULT = 70
GREETING_H_MAX = 100
GREETING_FONT_SIZE = 11
GREETING_PAD_X = 6
GREETING_PAD_Y = 4
MAX_GREETING_CHARS = 60

CHAT_ITEMS = [
    {"label": "RECORD", "description": "Reply to greeting", "action": "respond",
     "subtext": "Double-click to record"},
    {"label": "START NEW CHAT", "description": "Begin a new conversation", "action": "new_chat"},
    {"label": "RESUME CHAT", "description": "Continue last conversation", "action": "resume_chat", "subtext": ""},
    {"label": "CHAT HISTORY", "description": "Browse past conversations", "action": "chat_history"},
    {"label": "SETTINGS", "description": "Chat settings", "action": "settings"},
    {"label": "BACK TO MAIN MENU", "description": "Return to sidebar", "action": "back"},
]


class RecState(Enum):
    READY = auto()
    RECORDING = auto()
    TRANSCRIBING = auto()
    LAUNCHING = auto()
    ERROR = auto()


class ChatPreviewPanel(PreviewPanel):
    """Preview panel for CHAT sidebar item with inline recording."""

    def __init__(self, on_action: callable, repository=None,
                 audio_pipeline=None, stt_callable=None, led=None):
        items = [dict(item) for item in CHAT_ITEMS]
        super().__init__(items=items, on_action=on_action)
        self._repository = repository
        self._greeting_text: str = ""
        self._greeting_typewriter: TypewriterRenderer | None = None
        self._greeting_revealed = False
        self._cursor_anim = blink_cursor()
        self._greeting_session_id: int | None = None
        self._measured_greeting_h: int = GREETING_H_MIN

        # Recording state machine (accessed from STT thread + render thread)
        import threading as _threading
        self._rec_lock = _threading.Lock()
        self._rec_state = RecState.READY
        self._rec_start_time: float = 0.0
        self._rec_error_msg: str = ""
        self._cached_audio_path: str | None = None
        self._transcribed_text: str | None = None

        # Expansion animation
        self._launch_anim_frame: int = 0
        self._launch_anim_duration: int = 25  # frames (~1.7s at 15fps)
        self._launch_target_h: int = 0  # set dynamically from surface height
        self._launch_current_h: int = ITEM_H
        self._deferred_action: str | None = None  # fire on next update to avoid mid-frame stack changes

        # Dependencies
        self._audio_pipeline = audio_pipeline
        self._stt_callable = stt_callable
        self._led = led

    # ── Public API ──

    def set_greeting(self, text: str, session_id: int | None = None) -> None:
        """Set the agent greeting text and start slow typewriter."""
        self._greeting_text = text[:MAX_GREETING_CHARS] if text else ""
        self._greeting_session_id = session_id
        if self._greeting_text and not self._greeting_revealed:
            self._greeting_typewriter = TypewriterRenderer(self._greeting_text, speed="slow")
        else:
            self._greeting_revealed = True
            self._greeting_typewriter = None

    def set_resume_info(self, title: str, time_ago: str) -> None:
        """Update RESUME CHAT item with last chat info."""
        for item in self.items:
            if item["action"] == "resume_chat":
                item["subtext"] = f"{title} \u00b7 {time_ago}"
                break

    def set_audio_pipeline(self, pipeline, led=None):
        self._audio_pipeline = pipeline
        if led:
            self._led = led

    def set_stt_callable(self, stt_fn):
        self._stt_callable = stt_fn

    # ── Gesture routing ──

    def handle_action(self, action: str) -> bool:
        """Route gestures based on recording state."""
        if self._rec_state == RecState.RECORDING:
            if action in ("SHORT_PRESS", "DOUBLE_PRESS"):
                self._stop_inline_recording()
            elif action == "LONG_PRESS":
                self._cancel_inline_recording()
            return True

        if self._rec_state in (RecState.TRANSCRIBING, RecState.LAUNCHING):
            return True  # swallow everything

        if self._rec_state == RecState.ERROR:
            if action == "SHORT_PRESS":
                self._start_inline_recording()
            elif action == "LONG_PRESS":
                self._rec_state = RecState.READY
            return True

        # READY: check if activating the RECORD item
        if action == "DOUBLE_PRESS" and self.selected_index >= 0:
            item = self.items[self.selected_index]
            if item.get("action") == "respond":
                self._start_inline_recording()
                return True

        return super().handle_action(action)

    # ── Update loop ──

    def update(self, dt: float) -> None:
        # Fire deferred action first (from previous frame's animation completion)
        if self._deferred_action:
            action = self._deferred_action
            self._deferred_action = None
            try:
                self._on_action(action)
            except Exception:
                import logging as _log
                _log.getLogger(__name__).error("deferred action '%s' failed", action, exc_info=True)
            return  # skip rest of update this frame

        self._cursor_anim.update(dt)
        if self._greeting_typewriter and not self._greeting_typewriter.finished:
            self._greeting_typewriter.update(dt)
        elif self._greeting_typewriter and self._greeting_typewriter.finished:
            self._greeting_revealed = True
            self._greeting_typewriter = None

        # Expansion animation during LAUNCHING
        if self._rec_state == RecState.LAUNCHING:
            self._launch_anim_frame += 1
            target_h = self._launch_target_h or 208  # fallback to typical panel height
            t = min(1.0, self._launch_anim_frame / self._launch_anim_duration)
            eased = 1 - (1 - t) ** 3  # ease_out_cubic
            self._launch_current_h = int(ITEM_H + (target_h - ITEM_H) * eased)
            if t >= 1.0:
                self._rec_state = RecState.READY
                self._launch_current_h = ITEM_H
                # Defer to next frame so we don't modify screen stack mid-render
                self._deferred_action = "respond_with_text"

    # ── Render ──

    def render(self, surface: pygame.Surface) -> None:
        # Capture surface dimensions for launch animation
        self._surface_w = surface.get_width()
        self._surface_h = surface.get_height()
        if self._launch_target_h == 0:
            self._launch_target_h = self._surface_h

        font = get_font(GREETING_FONT_SIZE)
        w = surface.get_width()
        line_h = font.get_height() + 2

        # ── Dynamic greeting area ──
        greeting_h = GREETING_H_MIN
        if self._greeting_text:
            if self._greeting_typewriter:
                visible = self._greeting_typewriter.get_visible_text()
            else:
                visible = self._greeting_text

            lines = _wrap_text(visible, font, w - GREETING_PAD_X * 2)
            content_h = GREETING_PAD_Y + len(lines) * line_h + 4
            greeting_h = max(GREETING_H_MIN, min(content_h, GREETING_H_MAX))
            self._measured_greeting_h = greeting_h

            y = GREETING_PAD_Y
            for line in lines:
                if y + line_h > greeting_h - 4:
                    break
                surf = font.render(line, False, DIM3)
                surface.blit(surf, (GREETING_PAD_X, y))
                y += line_h

            # Blinking cursor while typing
            if self._greeting_typewriter and not self._greeting_typewriter.finished:
                cursor_char = "_" if self._cursor_anim.step == 0 else " "
                cursor_surf = font.render(cursor_char, False, DIM2)
                if lines:
                    last_line_w = font.size(lines[-1])[0]
                    cy = GREETING_PAD_Y + (len(lines) - 1) * line_h
                    surface.blit(cursor_surf, (GREETING_PAD_X + last_line_w, cy))
        else:
            self._measured_greeting_h = GREETING_H_MIN

        # Separator
        pygame.draw.line(surface, HAIRLINE,
                         (GREETING_PAD_X, greeting_h - 1),
                         (w - GREETING_PAD_X, greeting_h - 1))

        # ── Submenu items ──
        if self._rec_state == RecState.LAUNCHING:
            # Full-screen takeover banner
            self._render_launch_banner(surface)
        elif self._rec_state == RecState.READY:
            self._render_items(surface, y_offset=greeting_h)
        else:
            self._render_record_row_and_dimmed_items(surface, greeting_h)

    # ── Recording state rendering ──

    def _render_record_row(self, surface: pygame.Surface, y: int, w: int) -> int:
        """Render the RECORD row based on _rec_state. Returns row height used."""
        font = get_font(FONT_SIZE)
        subtext_font = get_font(FONT_SIZE - 2)

        if self._rec_state == RecState.RECORDING:
            now = time.time()
            # Red-tinted background (1Hz breathe)
            bg_pulse = (math.sin(now * 1.0 * 2 * math.pi) + 1) / 2
            bg_r = int(25 + 30 * bg_pulse)
            pygame.draw.rect(surface, (bg_r, 5, 5), pygame.Rect(0, y, w, ITEM_H))

            # Pulsing red dot (2Hz)
            dot_pulse = (math.sin(now * 2.0 * 2 * math.pi) + 1) / 2
            dot_bright = int(140 + 115 * dot_pulse)
            dot_r = 4 + int(dot_pulse)
            pygame.draw.circle(surface, (dot_bright, 20, 20),
                               (PAD_X + 6, y + ITEM_H // 2), dot_r)

            # Timer
            elapsed = int(now - self._rec_start_time)
            mins, secs = divmod(elapsed, 60)
            timer_surf = font.render(f"REC {mins}:{secs:02d}", False, (220, 80, 80))
            surface.blit(timer_surf, (PAD_X + 14, y + PAD_Y))

            # Hint
            hint = subtext_font.render("  Click to stop", False, DIM3)
            surface.blit(hint, (PAD_X, y + PAD_Y + font.get_height() + 1))
            return ITEM_H + subtext_font.get_height() + 2

        elif self._rec_state == RecState.TRANSCRIBING:
            dot_count = int(time.time() * 3.75) % 4
            dots = "." * dot_count
            text_surf = font.render("TRANSCRIBING" + dots, False, DIM2)
            surface.blit(text_surf, (PAD_X, y + PAD_Y))
            return ITEM_H

        elif self._rec_state == RecState.LAUNCHING:
            h = self._launch_current_h
            pygame.draw.rect(surface, (30, 30, 30), pygame.Rect(0, y, w, h))
            text_surf = font.render("STARTING CONVERSATION...", False, WHITE)
            tx = (w - text_surf.get_width()) // 2
            ty = y + (h - text_surf.get_height()) // 2
            surface.blit(text_surf, (tx, ty))
            return h

        elif self._rec_state == RecState.ERROR:
            text_surf = font.render(self._rec_error_msg or "ERROR", False, (220, 80, 80))
            surface.blit(text_surf, (PAD_X, y + PAD_Y))
            hint = subtext_font.render("  Click to retry", False, DIM3)
            surface.blit(hint, (PAD_X, y + PAD_Y + font.get_height() + 1))
            return ITEM_H + subtext_font.get_height() + 2

        return ITEM_H

    def _render_launch_banner(self, surface: pygame.Surface) -> None:
        """Full-screen takeover banner during LAUNCHING state."""
        w = surface.get_width()
        h = surface.get_height()

        # Dark background fills entire surface
        t = min(1.0, self._launch_anim_frame / self._launch_anim_duration)
        eased = 1 - (1 - t) ** 3  # ease_out_cubic
        bg_brightness = int(10 + 20 * eased)
        surface.fill((bg_brightness, bg_brightness, bg_brightness))

        # Expanding accent line from center
        line_w = int(w * eased)
        line_x = (w - line_w) // 2
        line_y = h // 2 - 20
        if line_w > 0:
            pygame.draw.line(surface, DIM2,
                             (line_x, line_y), (line_x + line_w, line_y))

        # "STARTING CONVERSATION..." — larger font, centered
        title_font = get_font(FONT_SIZE + 2)
        dot_count = int(time.time() * 3) % 4
        dots = "." * dot_count
        title_text = "STARTING CONVERSATION" + dots
        title_surf = title_font.render(title_text, False, WHITE)
        tx = (w - title_surf.get_width()) // 2
        ty = h // 2 - title_surf.get_height() // 2
        surface.blit(title_surf, (tx, ty))

        # Transcribed text below in dimmer, smaller font
        if self._transcribed_text:
            sub_font = get_font(FONT_SIZE - 2)
            # Word-wrap the transcribed text
            lines = _wrap_text(self._transcribed_text, sub_font, w - PAD_X * 4)
            sub_y = ty + title_surf.get_height() + 8
            for line in lines[:3]:  # max 3 lines
                sub_surf = sub_font.render(line, False, DIM3)
                sx = (w - sub_surf.get_width()) // 2
                surface.blit(sub_surf, (sx, sub_y))
                sub_y += sub_font.get_height() + 2

    def _render_record_row_and_dimmed_items(self, surface: pygame.Surface, y_offset: int) -> None:
        """Render custom RECORD row + dimmed remaining items."""
        font = get_font(FONT_SIZE)
        subtext_font = get_font(FONT_SIZE - 2)
        w = surface.get_width()

        y = y_offset
        row_h = self._render_record_row(surface, y, w)
        y += row_h

        # Remaining items dimmed
        for item in self.items[1:]:
            label = "  " + item["label"]
            text_surf = font.render(label, False, HAIRLINE)
            surface.blit(text_surf, (PAD_X, y + PAD_Y))

            item_h = ITEM_H
            subtext = item.get("subtext")
            if subtext:
                sub_surf = subtext_font.render("  " + subtext, False, HAIRLINE)
                surface.blit(sub_surf, (PAD_X, y + PAD_Y + font.get_height() + 1))
                item_h = ITEM_H + subtext_font.get_height() + 2

            if y + item_h - 1 < surface.get_height():
                pygame.draw.line(surface, HAIRLINE,
                                 (PAD_X, y + item_h - 1), (w - PAD_X, y + item_h - 1))
            y += item_h

    # ── Recording state machine ──

    def _start_inline_recording(self):
        self._rec_state = RecState.RECORDING
        self._rec_start_time = time.time()
        if self._audio_pipeline:
            self._audio_pipeline.start_recording()
        if self._led:
            try:
                self._led.recording()
            except Exception:
                pass

    def _stop_inline_recording(self):
        result = None
        if self._audio_pipeline:
            result = self._audio_pipeline.stop_and_process()
            self._cached_audio_path = getattr(result, 'path', None) if result else None
        self._rec_state = RecState.TRANSCRIBING
        if self._led:
            try:
                self._led.sending()
            except Exception:
                pass
        if self._stt_callable and self._cached_audio_path:
            threading.Thread(target=self._run_stt, daemon=True).start()
        else:
            # No STT — go straight to launching with empty text
            self._transcribed_text = ""
            self._rec_state = RecState.LAUNCHING
            self._launch_anim_frame = 0
            self._launch_current_h = ITEM_H

    def _cancel_inline_recording(self):
        if self._audio_pipeline:
            self._audio_pipeline.cancel()
        self._rec_state = RecState.READY
        self._cached_audio_path = None

    def _run_stt(self):
        try:
            text = self._stt_callable(self._cached_audio_path)
            if text and text.strip():
                with self._rec_lock:
                    self._transcribed_text = text.strip()
                    self._rec_state = RecState.LAUNCHING
                    self._launch_anim_frame = 0
                    self._launch_current_h = ITEM_H
                if self._led:
                    try:
                        self._led.success()
                    except Exception:
                        pass
            else:
                with self._rec_lock:
                    self._rec_state = RecState.ERROR
                    self._rec_error_msg = "NO AUDIO DETECTED"
        except Exception:
            with self._rec_lock:
                self._rec_state = RecState.ERROR
                self._rec_error_msg = "DIDN'T CATCH THAT"


def _wrap_text(text: str, font: pygame.font.Font, max_width: int) -> list[str]:
    """Simple word-wrap."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        if font.size(test)[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]
