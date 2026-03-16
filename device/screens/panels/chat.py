"""BITOS Chat Panel — gesture-driven voice-first chat with mode-based input."""
import json
import logging
import os
from collections import deque
from enum import Enum, auto
import threading
import time

import pygame

logger = logging.getLogger(__name__)

from health import ServiceHealth

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
from display.typewriter import TypewriterRenderer
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

        # Typewriter
        self._typewriter: TypewriterRenderer | None = None

        # Mode state
        self._mode = ChatMode.IDLE
        self._voice_stop_event = threading.Event()
        self._recording_cancelled = False
        self._recording_start_time: float = 0.0
        self._hold_timer: float | None = None
        self._quick_talk = False    # True if recording started via hold gesture
        self._action_template_index = 0
        self._voice_step = ""       # on-screen pipeline step callout
        self._voice_error = ""      # error detail shown on screen
        self._health = ServiceHealth()
        self._health_checked = False

        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
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
            latest = self._repository.get_latest_chat_session()
            if latest:
                age_seconds = time.time() - float(latest.get("updated_at", latest.get("created_at", 0.0)))
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
        # Check if hold has crossed the quick-talk threshold (600ms)
        if self._hold_timer is not None and self._mode == ChatMode.IDLE:
            if time.time() - self._hold_timer >= 0.6:
                self._hold_timer = None
                self._quick_talk = True
                self._start_recording()

        # Tick typewriter
        if self._typewriter and not self._typewriter.finished:
            self._typewriter.update(dt)
        elif self._typewriter and self._typewriter.finished and self._mode == ChatMode.STREAMING:
            # Typewriter done revealing — transition to SPEAKING or IDLE
            self._typewriter = None
            if self._audio_pipeline and self._messages:
                # TTS will be handled by _stream_response
                pass
            else:
                self._mode = ChatMode.IDLE

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
        # ── Hold gesture lifecycle (quick-talk) ──
        if action == "HOLD_START" and self._mode == ChatMode.IDLE:
            self._hold_timer = time.time()
            return
        if action == "HOLD_END":
            if self._mode == ChatMode.RECORDING and self._quick_talk:
                # Quick-talk: release → stop recording and send
                self._voice_stop_event.set()
            elif self._hold_timer is not None:
                # Hold released before threshold — ignored, SHORT_PRESS will fire
                self._hold_timer = None
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
            # Tap → field recording (toggle on)
            if self._hold_timer is not None:
                # Hold timer active — this tap came from a short hold, ignore
                self._hold_timer = None
                return
            self._quick_talk = False
            self._start_recording()
        elif action == "DOUBLE_PRESS":
            self._mode = ChatMode.ACTIONS
            self._action_template_index = 0

    def _handle_recording(self, action: str):
        if action == "SHORT_PRESS" and not self._quick_talk:
            # Field recording: tap again → stop and send
            self._voice_stop_event.set()
        elif action == "LONG_PRESS":
            # Cancel recording (either mode)
            self._recording_cancelled = True
            self._voice_stop_event.set()

    def _action_items(self) -> list[dict]:
        """Action menu: templates + navigation items."""
        return list(self._templates) + [
            {"label": "BACK", "message": ""},
            {"label": "BACK TO MAIN MENU", "message": ""},
        ]

    def _handle_actions(self, action: str):
        items = self._action_items()
        if action == "SHORT_PRESS":
            self._action_template_index = (self._action_template_index + 1) % len(items)
        elif action == "TRIPLE_PRESS":
            self._action_template_index = (self._action_template_index - 1) % len(items)
        elif action == "DOUBLE_PRESS":
            selected = items[self._action_template_index]
            if selected["label"] == "BACK":
                self._mode = ChatMode.IDLE
            elif selected["label"] == "BACK TO MAIN MENU":
                self._mode = ChatMode.IDLE
                if self._on_back:
                    self._on_back()
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

    def _get_action_bar_content(self) -> list[tuple[str, str]]:
        """Return action bar items for the current mode."""
        if self._mode == ChatMode.IDLE:
            return [("tap", "RECORD"), ("hold", "TALK"), ("double", "ACTIONS")]
        elif self._mode == ChatMode.RECORDING:
            if self._quick_talk:
                return [("hold", "RELEASE TO SEND")]
            return [("tap", "STOP & SEND"), ("hold", "CANCEL")]
        elif self._mode == ChatMode.ACTIONS:
            return [("tap", "NEXT"), ("double", "SELECT"), ("hold", "BACK")]
        elif self._mode == ChatMode.SPEAKING:
            return [("tap", "STOP")]
        return []  # STREAMING — render plain text instead

    @staticmethod
    def _split_into_pages(lines: list[str], lines_per_page: int, max_pages: int = 4) -> list[list[str]]:
        """Split wrapped lines into pages, preferring paragraph boundaries."""
        if not lines or lines_per_page <= 0:
            return [lines] if lines else [[]]

        total = len(lines)
        if total <= lines_per_page:
            return [lines]

        pages: list[list[str]] = []
        pos = 0

        while pos < total and len(pages) < max_pages:
            if len(pages) == max_pages - 1:
                # Last allowed page — take remaining, truncate if needed
                remaining = lines[pos:]
                if len(remaining) > lines_per_page:
                    page = remaining[:lines_per_page]
                    page[-1] = page[-1].rstrip() + "..."
                else:
                    page = remaining
                pages.append(page)
                break

            end = min(pos + lines_per_page, total)

            # Look for paragraph break (empty line) within ±2 lines of boundary
            best_break = None
            for i in range(max(pos + 1, end - 2), min(end + 3, total)):
                if i < total and lines[i].strip() == "":
                    best_break = i + 1  # include the empty line
                    break

            if best_break and best_break > pos:
                page = lines[pos:best_break]
            else:
                page = lines[pos:end]

            pages.append(page)
            pos += len(page)

        return pages if pages else [[]]

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

        # If typewriter is active, override last assistant message with revealed text
        if self._typewriter and snapshot and snapshot[-1]["role"] == "assistant":
            snapshot = list(snapshot)  # make mutable copy
            snapshot[-1] = {"role": "assistant", "text": self._typewriter.get_visible_text()}

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
            # Show recording elapsed + pipeline step
            elapsed = int(time.time() - self._recording_start_time)
            rec_text = f"RECORDING  {elapsed}s"
            rec_surf = self._font.render(rec_text, False, WHITE)
            surface.blit(rec_surf, (SAFE_INSET, action_top + 2))
        elif self._voice_step and self._voice_step not in ("", "SENDING"):
            # Show pipeline step callout (VALIDATING, TRANSCRIBING, ERROR)
            self._render_voice_callout(surface, action_top)

        # ── Action bar (gesture icons + labels) ──
        hint_y = PHYSICAL_H - SAFE_INSET - hint_h
        pygame.draw.line(surface, HAIRLINE, (0, hint_y), (PHYSICAL_W, hint_y))
        bar_center_y = hint_y + hint_h // 2
        bar_content = self._get_action_bar_content()

        if bar_content:
            # Render gesture icons with labels, evenly spaced
            items = []
            for icon_type, label in bar_content:
                label_surf = self._font_small.render(label, False, DIM2)
                items.append((icon_type, label_surf))

            total_w = sum(8 + 4 + s.get_width() for _, s in items)
            spacing = (PHYSICAL_W - total_w) // (len(items) + 1)
            bx = spacing
            for icon_type, label_surf in items:
                ic = (bx + 4, bar_center_y)
                if icon_type == "tap":
                    pygame.draw.circle(surface, DIM2, ic, 3, 1)
                elif icon_type == "double":
                    pygame.draw.circle(surface, DIM2, ic, 3, 1)
                    pygame.draw.circle(surface, DIM2, ic, 1, 1)
                elif icon_type == "hold":
                    pygame.draw.circle(surface, DIM2, ic, 3, 0)
                surface.blit(label_surf, (bx + 12, bar_center_y - label_surf.get_height() // 2))
                bx += 12 + label_surf.get_width() + spacing
        else:
            # Plain text mode (STREAMING) — show voice step if active
            step_label = self._voice_step.lower() if self._voice_step else "listening"
            stream_text = self._font_small.render(f"{step_label}...", False, DIM3)
            surface.blit(stream_text, ((PHYSICAL_W - stream_text.get_width()) // 2, bar_center_y - stream_text.get_height() // 2))

    def _render_actions_submenu(self, surface: pygame.Surface, top_y: int):
        """Render the templates sub-menu in the action area."""
        items = self._action_items()
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

    def _render_voice_callout(self, surface: pygame.Surface, top_y: int):
        """Show voice pipeline step + error detail in the action area."""
        step = self._voice_step
        error = self._voice_error
        is_error = step == "ERROR"

        # Step label (large)
        step_color = (255, 80, 80) if is_error else WHITE
        step_surf = self._font.render(step, False, step_color)
        surface.blit(step_surf, (SAFE_INSET, top_y + 2))

        # Error detail (smaller, below step)
        if error and error != step:
            err_surf = self._font_small.render(error[:28], False, DIM2)
            surface.blit(err_surf, (SAFE_INSET, top_y + self._ACTION_ROW_H + 2))

        # Pipeline progress dots: REC → VAL → API → STT → SEND
        stages = ["REC", "VAL", "API", "STT", "SEND"]
        stage_map = {
            "RECORDING": 0, "STOPPING": 0,
            "VALIDATING": 1,
            "PREFLIGHT": 2,
            "TRANSCRIBING": 3,
            "SENDING": 4,
            "ERROR": -1, "CANCELLED": -1,
        }
        current = stage_map.get(step, -1)
        dot_y = top_y + self._ACTION_ROW_H * 2 + 2
        dx = SAFE_INSET
        for i, label in enumerate(stages):
            if is_error:
                color = (255, 80, 80) if i <= max(current, 0) else DIM1
            elif i < current:
                color = DIM3  # completed
            elif i == current:
                color = WHITE  # active
            else:
                color = DIM1  # pending
            dot_surf = self._font_small.render(label, False, color)
            surface.blit(dot_surf, (dx, dot_y))
            dx += dot_surf.get_width() + 6

    def _start_recording(self):
        if self._mode == ChatMode.RECORDING or not self._audio_pipeline:
            return

        # Run health check on first recording attempt
        if not self._health_checked:
            self._health_checked = True
            self._health.check_all_async()

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

    def _set_voice_step(self, step: str, error: str = "") -> None:
        """Update on-screen voice pipeline callout. Shown in action area."""
        with self._messages_lock:
            self._voice_step = step
            self._voice_error = error
            self._status_detail = error if error else step

    def _do_voice_capture(self):
        import os

        self._set_voice_step("RECORDING")

        try:
            # ── Step 1: Start mic capture ──
            audio_path = self._audio_pipeline.record(max_seconds=30)
            if not audio_path:
                logger.error("mic_init_failed: record() returned None")
                self._set_voice_step("ERROR", "mic init failed")
                self._mode = ChatMode.IDLE
                if self._led:
                    self._led.error()
                return

            logger.info("voice_step=RECORDING path=%s", audio_path)

            # ── Step 2: Wait for button release or timeout ──
            self._voice_stop_event.wait(timeout=30)
            self._set_voice_step("STOPPING")
            self._audio_pipeline.stop_recording()

            if self._recording_cancelled:
                self._set_voice_step("CANCELLED")
                self._mode = ChatMode.IDLE
                if self._led:
                    self._led.off()
                return

            # ── Step 3: Validate WAV file ──
            self._set_voice_step("VALIDATING")
            time.sleep(0.3)  # flush wait

            if not os.path.exists(audio_path):
                logger.error("recording_file_missing path=%s", audio_path)
                self._set_voice_step("ERROR", "file missing")
                self._mode = ChatMode.IDLE
                if self._led:
                    self._led.error()
                return

            file_size = os.path.getsize(audio_path)
            logger.info("voice_step=VALIDATING size=%d path=%s", file_size, audio_path)

            if file_size <= 44:
                logger.error("recording_empty size=%d", file_size)
                self._set_voice_step("ERROR", f"empty ({file_size}B)")
                self._mode = ChatMode.IDLE
                if self._led:
                    self._led.error()
                return

            logger.info("voice_step=VALIDATED size=%d (%.1fs est)",
                        file_size, file_size / (16000 * 2))

            # Save for history
            self._save_recording(audio_path)

            # ── Step 4: Pre-flight check ──
            groq_health = self._health.get("groq")
            internet_health = self._health.get("internet")
            if internet_health and not internet_health["ok"]:
                self._set_voice_step("ERROR", "no internet")
                logger.error("voice_preflight: no internet — %s", internet_health["detail"])
                self._mode = ChatMode.IDLE
                if self._led:
                    self._led.error()
                return
            if groq_health and not groq_health["ok"]:
                detail = groq_health.get("detail", "groq fail")
                self._set_voice_step("ERROR", detail)
                logger.error("voice_preflight: groq fail — %s", detail)
                self._mode = ChatMode.IDLE
                if self._led:
                    self._led.error()
                return

            # ── Step 5: Transcribe ──
            self._mode = ChatMode.STREAMING
            self._set_voice_step("TRANSCRIBING")
            logger.info("voice_step=TRANSCRIBING engine=%s",
                        getattr(self._audio_pipeline, '_stt_engine', '?'))

            text = self._audio_pipeline.transcribe(audio_path).strip()
            logger.info("voice_step=TRANSCRIBED len=%d text=%s",
                        len(text), text[:80] if text else "(empty)")

        except Exception as exc:
            err_short = str(exc)[:30]
            logger.error("voice_capture_failed: %s", exc, exc_info=True)
            self._set_voice_step("ERROR", err_short)
            self._mode = ChatMode.IDLE
            if self._led:
                self._led.error()
            self._mark_failed("", "unknown", False,
                              custom_copy=f"voice: {err_short}")
            return

        if self._led:
            self._led.off()

        if not text:
            self._set_voice_step("ERROR", "no speech detected")
            self._mode = ChatMode.IDLE
            return

        # ── Step 5: Send to backend ──
        self._set_voice_step("SENDING")
        self._input_text = text
        self._send_message()

    def _save_recording(self, audio_path: str) -> None:
        """Copy recording to persistent storage for history/re-transcription."""
        import os
        import shutil

        save_dir = os.path.join(os.environ.get("BITOS_DATA_DIR", "device/data"), "recordings")
        try:
            os.makedirs(save_dir, exist_ok=True)
            dest = os.path.join(save_dir, os.path.basename(audio_path))
            shutil.copy2(audio_path, dest)
            logger.info("recording_saved dest=%s", dest)
        except Exception as exc:
            logger.warning("recording_save_failed: %s", exc)

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

            # Feed completed response to typewriter for progressive reveal
            speed = "normal"
            if self._repository:
                saved_speed = self._repository.get_setting("text_speed", None)
                if saved_speed:
                    speed = str(saved_speed)
            self._typewriter = TypewriterRenderer(response_text, speed=speed)

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
                except Exception as tts_exc:
                    logger.error("tts_failed: %s", tts_exc)

            with self._messages_lock:
                self._status = self.STATUS_CONNECTED
                self._status_detail = ""
                self._voice_step = ""
                self._voice_error = ""
                self._last_failed_message = None
                self._last_error_retryable = False
        except BackendChatError as exc:
            self._mark_failed(message, exc.kind, exc.retryable)
        except Exception as exc:
            logger.error("stream_response_failed: %s", exc, exc_info=True)
            self._mark_failed(message, "unknown", True, custom_copy=f"error: {str(exc)[:30]}")
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
            # Show health summary if checks have run
            if self._health_checked and self._health.is_complete():
                if not self._health.all_ok():
                    return self._health.summary_line()[:24]
            return "connected"
        if self._status == self.STATUS_RETRYING:
            return "retrying"
        if self._status_detail:
            return self._status_detail
        return self._status

    def _status_color(self):
        if self._status == self.STATUS_CONNECTED:
            # Red-ish if health check failed
            if self._health_checked and self._health.is_complete() and not self._health.all_ok():
                return (255, 120, 80)
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
