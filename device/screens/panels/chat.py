"""
BITOS Chat Panel (Phase 2 — reliability UX)
Text input via keyboard/button, streaming response rendered line-by-line.
"""
import json
from collections import deque
import threading
import time

import pygame

from screens.base import BaseScreen
from display.tokens import (
    BLACK,
    WHITE,
    DIM1,
    DIM2,
    DIM3,
    HAIRLINE,
    PHYSICAL_W,
    PHYSICAL_H,
    STATUS_BAR_H,
)
from display.animator import blink_cursor
from display.theme import merge_runtime_ui_settings, load_ui_font, ui_line_height
from client.api import BackendClient, BackendChatError
from audio import AudioPipeline
from storage.repository import DeviceRepository


DEFAULT_TEMPLATES = [
    {
        "label": "MORNING BRIEF",
        "message": "Quick rundown: my tasks today, anything time-sensitive, and what I should focus on first.",
    },
    {
        "label": "TENDER FEST",
        "message": "Let's brainstorm Tender Fest. Current directions: No Tender Left Behind, sauce themes, Heinz sponsor angle. What should we explore?",
    },
    {
        "label": "QUICK TASK",
        "message": "What are my most urgent tasks right now? Which one first and why?",
    },
    {
        "label": "HACKER MODE",
        "message": "What's the most important thing to fix or build in BITOS right now?",
    },
]


class ChatPanel(BaseScreen):
    """Chat panel with reliability status and retry controls."""
    _owns_status_bar = True

    STATUS_CONNECTED = "connected"
    STATUS_RETRYING = "retrying"
    STATUS_OFFLINE = "offline"
    STATUS_DEGRADED = "degraded"

    ERROR_MESSAGES = {
        "offline": "Server offline",
        "timeout": "Server timeout",
        "auth": "auth failed",
        "rate_limit": "rate limited",
        "upstream": "provider busy",
        "network": "network unstable",
        "request": "request failed",
        "unknown": "unknown error",
    }

    def __init__(self, client: BackendClient, ui_settings: dict | None = None, repository: DeviceRepository | None = None, audio_pipeline: AudioPipeline | None = None, led=None, on_back=None):
        self._client = client
        self._cursor_anim = blink_cursor()
        self._repository = repository
        self._on_back = on_back
        self._messages_lock = threading.Lock()
        self._audio_pipeline = audio_pipeline
        self._led = led

        # State
        self._input_text = ""
        self._messages = deque(maxlen=50)  # {"role": "user"|"assistant", "text": "..."}
        self._is_streaming = False
        self._scroll_offset = 0
        self._status = self.STATUS_CONNECTED
        self._status_detail = ""
        self._last_failed_message: str | None = None
        self._last_error_retryable = False
        self._session_id = None
        self._template_index = 0
        self._templates = list(DEFAULT_TEMPLATES)
        self._resumed_until = 0.0

        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)
        self._line_height = ui_line_height(self._font, self._ui_settings)

        if self._repository:
            raw = self._repository.get_setting("chat_templates", None)
            if raw:
                try:
                    loaded = json.loads(raw)
                    if isinstance(loaded, list):
                        self._templates = loaded
                except Exception:
                    pass
            self._resumed_until = 0.0
            latest = self._repository.get_latest_session()
            if latest:
                age_seconds = time.time() - float(latest.get("created_at", 0.0))
                if age_seconds <= 24 * 3600:
                    self._session_id = int(latest["id"])
                    restored = self._repository.get_session_messages(str(self._session_id), limit=10)
                    if restored:
                        with self._messages_lock:
                            self._messages = deque(({"role": m["role"], "text": m["text"]} for m in restored), maxlen=50)
                            self._status_detail = "SESSION RESTORED"
                            self._resumed_until = time.time() + 2.0
                            self._scroll_offset = 0

    def update(self, dt: float):
        self._cursor_anim.update(dt)

    def handle_input(self, event: pygame.event.Event):
        if event.type != pygame.KEYDOWN:
            return

        if event.key == pygame.K_r and self._can_retry():
            self._retry_last_failed()
            return

        if self._is_streaming:
            return  # Ignore input while streaming

        if event.key == pygame.K_RETURN:
            self._send_message()
        elif event.key == pygame.K_BACKSPACE:
            self._input_text = self._input_text[:-1]
        elif event.key == pygame.K_UP:
            self._scroll_offset = max(0, self._scroll_offset - 1)
        elif event.key == pygame.K_DOWN:
            self._scroll_offset += 1
        elif event.unicode and event.unicode.isprintable():
            self._input_text += event.unicode

    def handle_action(self, action: str):
        if action == "SHORT_PRESS" and self._audio_pipeline and self._audio_pipeline.is_speaking():
            # VERIFIED: SHORT_PRESS while TTS is active immediately stops speech and shows "speech stopped".
            self._audio_pipeline.stop_speaking()
            with self._messages_lock:
                self._status_detail = "speech stopped"
            return

        if self._showing_templates() and action == "SHORT_PRESS":
            if self._templates:
                self._template_index = (self._template_index + 1) % len(self._templates)
            return
        if action == "SHORT_PRESS":
            self._scroll_offset += 1
            return

        if action == "TRIPLE_PRESS":
            self._session_id = self._repository.create_session(title="NEW CHAT") if self._repository else None
            with self._messages_lock:
                self._messages = deque(maxlen=50)
                self._input_text = ""
                self._status_detail = "new chat"
            return

        if action == "DOUBLE_PRESS":
            if self._on_back:
                self._on_back()
            return

        if action == "LONG_PRESS":
            # VERIFIED: LONG_PRESS in chat starts voice capture and status updates to "recording...".
            if self._showing_templates() and self._templates:
                self._send_template_message(self._templates[self._template_index])
                return
            if self._can_retry():
                self._retry_last_failed()
            else:
                self._capture_voice_input()

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # ── Status bar: 18px, dark variant (black bg, white text, hairline border) ──
        pygame.draw.line(surface, HAIRLINE, (0, STATUS_BAR_H - 1), (PHYSICAL_W, STATUS_BAR_H - 1))
        header_text = self._font_small.render("CHAT", False, WHITE)
        surface.blit(header_text, (6, (STATUS_BAR_H - header_text.get_height()) // 2))

        status_copy = self._status_copy()
        status_color = self._status_color()
        status_surface = self._font_small.render(status_copy, False, status_color)
        status_x = max(70, PHYSICAL_W - status_surface.get_width() - 6)
        surface.blit(status_surface, (status_x, (STATUS_BAR_H - status_surface.get_height()) // 2))

        # ── Messages area ──
        msg_y = STATUS_BAR_H + 2
        max_y = PHYSICAL_H - 26  # Leave room for input bar + hint

        with self._messages_lock:
            snapshot = list(self._messages)

        visible_lines = []
        for msg in snapshot:
            prefix = "> " if msg["role"] == "user" else ""
            color = DIM2 if msg["role"] == "user" else WHITE
            lines = self._wrap_text(prefix + msg["text"], PHYSICAL_W - 8)
            for line in lines:
                visible_lines.append((line, color))

        if self._showing_templates():
            msg_y = self._render_templates(surface=surface, start_y=msg_y, max_y=max_y)
        else:
            start = max(0, len(visible_lines) - int((max_y - msg_y) / self._line_height) - self._scroll_offset)
            for line_text, color in visible_lines[start:]:
                if msg_y > max_y:
                    break
                text_surface = self._font.render(line_text, False, color)
                surface.blit(text_surface, (4, msg_y))
                msg_y += self._line_height

        # ── Streaming indicator / retry hint + queue debug status ──
        if self._is_streaming:
            dots = "." * ((pygame.time.get_ticks() // 400) % 4)
            indicator = self._font_small.render(dots, False, DIM3)
            surface.blit(indicator, (4, max_y - 8))
        elif self._can_retry():
            hint = self._font_small.render("R/LONG: retry", False, DIM1)
            surface.blit(hint, (4, max_y - 8))

        queue_status = self._queue_status_copy()
        if queue_status:
            queue_surface = self._font_small.render(queue_status, False, DIM2)
            queue_x = max(96, PHYSICAL_W - queue_surface.get_width() - 4)
            surface.blit(queue_surface, (queue_x, max_y - 8))

        # ── Input bar ──
        input_y = PHYSICAL_H - 20
        pygame.draw.line(surface, HAIRLINE, (0, input_y - 2), (PHYSICAL_W, input_y - 2))

        display_text = self._input_text
        if len(display_text) > 28:
            display_text = "..." + display_text[-25:]

        input_surface = self._font.render(display_text, False, WHITE)
        surface.blit(input_surface, (4, input_y))

        if not self._is_streaming and self._cursor_anim.step == 0:
            cursor_x = 4 + input_surface.get_width() + 1
            pygame.draw.rect(surface, WHITE, (cursor_x, input_y, 6, self._font.get_height()))

        # ── Key hint bar ──
        if self._showing_templates():
            hint_text = "SHORT:NEXT \u00b7 LONG:SEND \u00b7 DBL:BACK"
        else:
            hint_text = "SHORT:SCROLL \u00b7 LONG:VOICE \u00b7 DBL:BACK"
        hint = self._font_hint.render(hint_text, False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 1))


    def _capture_voice_input(self):
        if self._is_streaming or not self._audio_pipeline:
            return
        self._is_streaming = True
        if self._led:
            self._led.listening()
        with self._messages_lock:
            self._status = self.STATUS_CONNECTED
            self._status_detail = "recording..."
        threading.Thread(target=self._do_voice_capture, daemon=True).start()

    def _do_voice_capture(self):
        import time as _time

        timeout_seconds = 30
        try:
            audio_path = self._audio_pipeline.record(max_seconds=timeout_seconds)
            if not audio_path:
                self._is_streaming = False
                if self._led:
                    self._led.off()
                return
            _time.sleep(timeout_seconds)
            self._audio_pipeline.stop_recording()
            with self._messages_lock:
                self._status_detail = "Recording stopped (30s max)"
            text = self._audio_pipeline.transcribe(audio_path).strip()
        except Exception as exc:
            self._is_streaming = False
            if self._led:
                self._led.error()
            self._mark_failed("", "unknown", False)
            self._status_detail = f"voice err: {str(exc)[:20]}"
            return

        self._is_streaming = False
        if self._led:
            self._led.off()
        if not text:
            with self._messages_lock:
                self._status_detail = "Didn't catch that — try again"
            return
        self._input_text = text
        self._send_message()

    def _send_message(self):
        text = self._input_text.strip()
        if not text:
            return

        with self._messages_lock:
            self._messages.append({"role": "user", "text": text})

        if self._repository:
            if self._session_id is None:
                self._session_id = self._repository.create_session(title=text[:24])
            self._repository.add_message(self._session_id, "user", text)

        self._input_text = ""
        self._is_streaming = True
        self._scroll_offset = 0
        self._status = self.STATUS_CONNECTED
        self._status_detail = ""
        self._last_failed_message = None
        self._last_error_retryable = False

        if self._led:
            self._led.thinking()
        thread = threading.Thread(target=self._stream_response, args=(text,), daemon=True)
        thread.start()

    def _send_template_message(self, template: dict) -> None:
        message = str(template.get("message", "")).strip()
        if not message:
            return
        self._input_text = message
        self._send_message()

    def _retry_last_failed(self):
        if not self._last_failed_message or self._is_streaming:
            return

        self._is_streaming = True
        self._status = self.STATUS_RETRYING
        self._status_detail = ""

        thread = threading.Thread(target=self._stream_response, args=(self._last_failed_message,), daemon=True)
        thread.start()

    def _stream_response(self, message: str):
        try:
            response_text = ""
            with self._messages_lock:
                self._messages.append({"role": "assistant", "text": ""})

            result = self._client.chat(message)
            if isinstance(result, dict) and result.get("error"):
                kind = str(result.get("kind", "unknown"))
                retryable = bool(result.get("retryable", True))
                self._mark_failed(message, kind, retryable, custom_copy=str(result.get("error")))
                return

            for chunk in result:
                response_text += chunk
                with self._messages_lock:
                    self._messages[-1]["text"] = response_text

            if self._repository and self._session_id is not None:
                self._repository.add_message(self._session_id, "assistant", response_text)

            if self._audio_pipeline and response_text:
                try:
                    with self._messages_lock:
                        self._status_detail = "◎ SPEAKING..."
                    if self._led:
                        self._led.speaking()
                    self._audio_pipeline.speak(response_text)
                except Exception:
                    pass

            with self._messages_lock:
                self._status = self.STATUS_CONNECTED
                self._status_detail = ""
                self._last_failed_message = None
                self._last_error_retryable = False
        except BackendChatError as exc:
            self._mark_failed(message, exc.kind, exc.retryable)
        except Exception:
            self._mark_failed(message, "unknown", True)
        finally:
            self._is_streaming = False
            if self._led and self._status == self.STATUS_CONNECTED:
                self._led.off()

    def _mark_failed(self, message: str, kind: str, retryable: bool, custom_copy: str | None = None):
        status = self.STATUS_OFFLINE if kind in ("offline", "network") else self.STATUS_DEGRADED
        error_copy = custom_copy or self.ERROR_MESSAGES.get(kind, self.ERROR_MESSAGES["unknown"])

        if self._led:
            self._led.error()
        with self._messages_lock:
            self._status = status
            self._status_detail = error_copy
            self._last_error_retryable = retryable
            self._last_failed_message = message if retryable else None
            self._input_text = message
            self._messages.append({"role": "assistant", "text": f"[{error_copy}]"})

        if self._repository and self._session_id is not None:
            self._repository.add_message(self._session_id, "assistant", f"[{error_copy}]")

    def _can_retry(self) -> bool:
        return bool(self._last_failed_message and self._last_error_retryable and not self._is_streaming)

    def _status_copy(self) -> str:
        if self._resumed_until and time.time() < self._resumed_until:
            return "SESSION RESTORED"
        if self._status == self.STATUS_CONNECTED:
            return "connected"
        if self._status == self.STATUS_RETRYING:
            return "retrying"
        if self._status_detail:
            return self._status_detail
        return self._status

    def _status_color(self):
        if self._status == self.STATUS_CONNECTED:
            return DIM1
        if self._status == self.STATUS_RETRYING:
            return DIM2
        return WHITE

    def _wrap_text(self, text: str, max_width: int) -> list[str]:
        """Simple character-level word wrap."""
        lines = []
        current = ""
        for char in text:
            if char == "\n":
                lines.append(current)
                current = ""
                continue
            test = current + char
            w = self._font.size(test)[0]
            if w <= max_width:
                current = test
            else:
                lines.append(current)
                current = char
        if current:
            lines.append(current)
        return lines or [""]

    def _showing_templates(self) -> bool:
        return not self._messages and bool(self._templates)

    def _render_templates(self, surface: pygame.Surface, start_y: int, max_y: int) -> int:
        y = start_y
        row_h = max(self._line_height, 20)
        for idx, template in enumerate(self._templates):
            if y > max_y:
                break
            label = str(template.get("label", "TEMPLATE"))
            focused = idx == self._template_index
            if focused:
                pygame.draw.rect(surface, WHITE, pygame.Rect(0, y - 2, PHYSICAL_W, row_h + 2))
            text_color = BLACK if focused else DIM2
            text_surface = self._font.render(label, False, text_color)
            surface.blit(text_surface, (8, y))
            y += row_h
        return y


    def get_active_compose_target(self) -> str | None:
        return "compose_body"

    def receive_keyboard_input(self, target: str, text: str, cursor: int) -> bool:
        if target not in {"any", "compose_body", "search"}:
            return False
        self._input_text = text
        _ = cursor
        return True

    def _queue_status_copy(self) -> str:
        """Compact queue/dead-letter debug status for tiny-screen visibility."""
        if not self._repository:
            return ""
        try:
            metrics = self._repository.queue_metrics()
            queue_depth = int(metrics.get("queue_depth", 0))
            dead = int(metrics.get("dead_letter", 0))
            copy = f"q:{queue_depth} d:{dead}"
            if dead <= 0:
                return copy

            dead_letters = self._repository.queue_list_dead_letters(limit=1)
            if dead_letters and dead_letters[0].get("last_error"):
                reason = str(dead_letters[0]["last_error"]).replace("_", "-")[:8]
                return f"{copy} {reason}"
            return copy
        except Exception:
            return ""
