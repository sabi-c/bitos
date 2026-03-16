"""BITOS Chat Panel — gesture-driven voice-first chat with mode-based input."""
import json
from collections import deque
from enum import Enum, auto
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
    SAFE_INSET,
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


class ChatMode(Enum):
    IDLE = auto()       # Viewing chat history
    RECORDING = auto()  # Capturing audio
    ACTIONS = auto()    # Quick actions template menu
    STREAMING = auto()  # Response arriving
    SPEAKING = auto()   # TTS playing response


class ChatPanel(BaseScreen):
    """Gesture-driven voice-first chat panel with mode-based input routing."""
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

    # Layout constants
    _ACTION_ROW_H = 18
    _HINT_H = 20

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
        self._templates = list(DEFAULT_TEMPLATES)
        self._resumed_until = 0.0

        # Mode state
        self._mode = ChatMode.IDLE
        self._voice_stop_event = threading.Event()
        self._recording_cancelled = False
        self._recording_start_time: float = 0.0
        self._hold_timer: float | None = None
        self._action_template_index = 0

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
        # Check if hold has crossed the recording threshold (400ms)
        if self._hold_timer is not None and self._mode == ChatMode.IDLE:
            if time.time() - self._hold_timer >= 0.4:
                self._hold_timer = None
                self._start_recording()

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
        # HOLD_START/HOLD_END for hold-to-record
        if action == "HOLD_START" and self._mode == ChatMode.IDLE:
            self._hold_timer = time.time()
            return
        if action == "HOLD_END":
            self._hold_timer = None  # Release doesn't stop recording
            return

        # Dispatch to mode-specific handler
        handler = {
            ChatMode.IDLE: self._handle_idle,
            ChatMode.RECORDING: self._handle_recording,
            ChatMode.ACTIONS: self._handle_actions,
            ChatMode.STREAMING: self._handle_streaming,
            ChatMode.SPEAKING: self._handle_speaking,
        }.get(self._mode)
        if handler:
            handler(action)

    def _handle_idle(self, action: str):
        if action == "SHORT_PRESS":
            self._scroll_offset = max(0, self._scroll_offset - 1)
        elif action == "TRIPLE_PRESS":
            self._scroll_offset += 1
        elif action == "DOUBLE_PRESS":
            self._mode = ChatMode.ACTIONS
            self._action_template_index = 0
        elif action == "LONG_PRESS":
            if self._on_back:
                self._on_back()

    def _handle_recording(self, action: str):
        if action in ("SHORT_PRESS", "DOUBLE_PRESS"):
            # Send recording
            self._voice_stop_event.set()
        elif action == "LONG_PRESS":
            # Cancel recording
            self._recording_cancelled = True
            self._voice_stop_event.set()

    def _handle_actions(self, action: str):
        items = list(self._templates) + [{"label": "BACK", "message": ""}]
        if action == "SHORT_PRESS":
            self._action_template_index = (self._action_template_index + 1) % len(items)
        elif action == "TRIPLE_PRESS":
            self._action_template_index = (self._action_template_index - 1) % len(items)
        elif action == "DOUBLE_PRESS":
            selected = items[self._action_template_index]
            if selected["label"] == "BACK":
                self._mode = ChatMode.IDLE
            else:
                self._send_template_message(selected)
                self._mode = ChatMode.IDLE
        elif action == "LONG_PRESS":
            self._mode = ChatMode.IDLE

    def _handle_streaming(self, action: str):
        pass  # Ignore all input while response is streaming

    def _handle_speaking(self, action: str):
        if action in ("SHORT_PRESS", "DOUBLE_PRESS", "LONG_PRESS"):
            if self._audio_pipeline:
                self._audio_pipeline.stop_speaking()
            self._mode = ChatMode.IDLE
            with self._messages_lock:
                self._status_detail = ""

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # ── Status bar (20px) ──
        pygame.draw.line(surface, HAIRLINE, (0, SAFE_INSET + STATUS_BAR_H - 1), (PHYSICAL_W, SAFE_INSET + STATUS_BAR_H - 1))
        header_text = self._font_small.render("CHAT", False, WHITE)
        surface.blit(header_text, (SAFE_INSET, SAFE_INSET + (STATUS_BAR_H - header_text.get_height()) // 2))

        # Recording indicator or connection status
        if self._mode == ChatMode.RECORDING:
            # Pulsing red dot
            pulse = (pygame.time.get_ticks() // 500) % 2 == 0
            rec_color = (255, 60, 60) if pulse else DIM1
            rec_surface = self._font_small.render("\u25cfREC", False, rec_color)
            rec_x = PHYSICAL_W - rec_surface.get_width() - SAFE_INSET
            surface.blit(rec_surface, (rec_x, SAFE_INSET + (STATUS_BAR_H - rec_surface.get_height()) // 2))
        else:
            status_copy = self._status_copy()
            status_color = self._status_color()
            status_surface = self._font_small.render(status_copy, False, status_color)
            status_x = max(70, PHYSICAL_W - status_surface.get_width() - SAFE_INSET)
            surface.blit(status_surface, (status_x, SAFE_INSET + (STATUS_BAR_H - status_surface.get_height()) // 2))

        # ── Layout calculations ──
        action_menu_h = self._ACTION_ROW_H * 3
        hint_h = self._HINT_H
        msg_area_top = SAFE_INSET + STATUS_BAR_H + 2
        msg_area_bottom = PHYSICAL_H - SAFE_INSET - action_menu_h - hint_h - 2

        # ── Messages area ──
        with self._messages_lock:
            snapshot = list(self._messages)

        visible_lines = []
        for msg in snapshot:
            prefix = "> " if msg["role"] == "user" else ""
            color = DIM2 if msg["role"] == "user" else WHITE
            lines = self._wrap_text(prefix + msg["text"], PHYSICAL_W - SAFE_INSET * 2)
            for line in lines:
                visible_lines.append((line, color))

        msg_y = msg_area_top
        max_visible = int((msg_area_bottom - msg_area_top) / self._line_height)
        start = max(0, len(visible_lines) - max_visible - self._scroll_offset)
        for line_text, color in visible_lines[start:]:
            if msg_y > msg_area_bottom:
                break
            text_surface = self._font.render(line_text, False, color)
            surface.blit(text_surface, (SAFE_INSET, msg_y))
            msg_y += self._line_height

        # ── Streaming indicator / retry hint ──
        if self._is_streaming:
            dots = "." * ((pygame.time.get_ticks() // 400) % 4)
            indicator = self._font_small.render(dots, False, DIM3)
            surface.blit(indicator, (4, msg_area_bottom - 8))
        elif self._can_retry():
            hint = self._font_small.render("DBL: retry", False, DIM1)
            surface.blit(hint, (4, msg_area_bottom - 8))

        queue_status = self._queue_status_copy()
        if queue_status:
            queue_surface = self._font_small.render(queue_status, False, DIM2)
            queue_x = max(96, PHYSICAL_W - queue_surface.get_width() - 4)
            surface.blit(queue_surface, (queue_x, msg_area_bottom - 8))

        # ── Action area ──
        action_top = PHYSICAL_H - SAFE_INSET - action_menu_h - hint_h
        pygame.draw.line(surface, HAIRLINE, (0, action_top - 1), (PHYSICAL_W, action_top - 1))

        if self._mode == ChatMode.ACTIONS:
            self._render_actions_submenu(surface, action_top)
        elif self._mode == ChatMode.RECORDING:
            # Show recording elapsed time
            elapsed = int(time.time() - self._recording_start_time)
            rec_text = f"RECORDING  {elapsed}s"
            rec_surf = self._font.render(rec_text, False, WHITE)
            surface.blit(rec_surf, (SAFE_INSET, action_top + self._ACTION_ROW_H))

        # ── Hint bar ──
        hint_y = PHYSICAL_H - SAFE_INSET - hint_h
        if self._mode == ChatMode.RECORDING:
            hint_text = "TAP:SEND \u00b7 LONG:CANCEL"
        elif self._mode == ChatMode.ACTIONS:
            hint_text = "SHORT:NEXT \u00b7 DBL:SEL \u00b7 LONG:BACK"
        elif self._mode == ChatMode.SPEAKING:
            hint_text = "TAP:STOP"
        elif self._mode == ChatMode.STREAMING:
            hint_text = "listening..."
        else:
            hint_text = "HOLD:RECORD \u00b7 DBL:ACTIONS \u00b7 LONG:BACK"
        hint = self._font_hint.render(hint_text, False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, hint_y))

    def _render_actions_submenu(self, surface: pygame.Surface, top_y: int):
        """Render the templates sub-menu in the action area."""
        items = list(self._templates) + [{"label": "BACK", "message": ""}]
        # Show 3 rows centered around selected index
        visible_count = 3
        start_idx = max(0, self._action_template_index - 1)
        if start_idx + visible_count > len(items):
            start_idx = max(0, len(items) - visible_count)

        for row in range(visible_count):
            idx = start_idx + row
            if idx >= len(items):
                break
            y = top_y + row * self._ACTION_ROW_H
            focused = idx == self._action_template_index
            label = str(items[idx].get("label", ""))
            prefix = "> " if focused else "- "
            text_color = WHITE if focused else DIM2
            row_surface = self._font.render(prefix + label, False, text_color)
            surface.blit(row_surface, (SAFE_INSET, y + 1))

    def _start_recording(self):
        if self._mode == ChatMode.RECORDING or not self._audio_pipeline:
            return
        self._mode = ChatMode.RECORDING
        self._recording_cancelled = False
        self._voice_stop_event.clear()
        self._recording_start_time = time.time()
        if self._led:
            self._led.listening()
        with self._messages_lock:
            self._status = self.STATUS_CONNECTED
            self._status_detail = "recording..."
        threading.Thread(target=self._do_voice_capture, daemon=True).start()

    def _do_voice_capture(self):
        try:
            audio_path = self._audio_pipeline.record(max_seconds=30)
            if not audio_path:
                self._mode = ChatMode.IDLE
                if self._led:
                    self._led.off()
                return

            # Wait for stop event (set by button press) or timeout
            self._voice_stop_event.wait(timeout=30)
            self._audio_pipeline.stop_recording()

            if self._recording_cancelled:
                self._mode = ChatMode.IDLE
                with self._messages_lock:
                    self._status_detail = "cancelled"
                if self._led:
                    self._led.off()
                return

            self._mode = ChatMode.STREAMING
            with self._messages_lock:
                self._status_detail = "transcribing..."
            text = self._audio_pipeline.transcribe(audio_path).strip()
        except Exception as exc:
            self._mode = ChatMode.IDLE
            if self._led:
                self._led.error()
            self._mark_failed("", "unknown", False)
            self._status_detail = f"voice err: {str(exc)[:20]}"
            return

        if self._led:
            self._led.off()
        if not text:
            with self._messages_lock:
                self._status_detail = "Didn't catch that"
            self._mode = ChatMode.IDLE
            return
        self._input_text = text
        self._send_message()

    def _send_message(self):
        text = self._input_text.strip()
        if not text:
            return

        self._mode = ChatMode.STREAMING

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
                    self._mode = ChatMode.SPEAKING
                    with self._messages_lock:
                        self._status_detail = "SPEAKING..."
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
            if self._mode in (ChatMode.STREAMING, ChatMode.SPEAKING):
                self._mode = ChatMode.IDLE
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
