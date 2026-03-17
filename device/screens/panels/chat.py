"""BITOS Chat Panel — gesture-driven voice-first chat with mode-based input."""
import json
import logging
import os
import re
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
from display.pagination import split_into_pages as _shared_split_into_pages
from display.pagination import wrap_text as _shared_wrap_text
from display.typewriter import TypewriterRenderer, TypewriterConfig
from display.theme import merge_runtime_ui_settings, load_ui_font, ui_line_height
from display.markdown import parse_line, wrap_markdown_text, STYLE_BOLD, STYLE_ITALIC, STYLE_CODE, STYLE_HEADER, STYLE_BULLET
from client.api import BackendClient, BackendChatError
from audio import AudioPipeline
from storage.repository import DeviceRepository
from overlays.speaking_overlay import SpeakingOverlay
import display.tokens as tokens_module


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


def _should_speak(voice_mode: str, agent_voice_enabled: bool, has_api_key: bool) -> bool:
    """Determine if TTS should fire based on user setting, agent preference, and API key."""
    if not has_api_key:
        return False
    if voice_mode == "off":
        return False
    if voice_mode == "on":
        return True
    # auto — agent decides
    return agent_voice_enabled


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

    def __init__(self, client: BackendClient, ui_settings: dict | None = None, repository: DeviceRepository | None = None, audio_pipeline: AudioPipeline | None = None, led=None, on_back=None, on_settings=None, mode: str = "auto", session_id: int | None = None):
        self._client = client
        self._cursor_anim = blink_cursor()
        self._repository = repository
        self._on_back = on_back
        self._on_settings = on_settings
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
        self._user_typewriter: TypewriterRenderer | None = None  # types out user's sent text

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
        self._confirm_tap_until: float = 0.0  # tap-to-record confirmation window
        self._post_speaking_until: float = 0.0  # cooldown after TTS skip
        self._health = ServiceHealth()
        self._health_checked = False
        self._speaking_overlay = SpeakingOverlay()

        # Pagination state
        self._pages: list[list[str]] = []
        self._current_page: int = 0
        self._page_revealed: list[bool] = []
        self._page_typewriter: TypewriterRenderer | None = None
        self._context_header: str = ""
        self._user_browsing: bool = False  # True when user manually navigated pages

        # Speech queue: (text, user_message) tuples waiting for TTS
        self._speech_queue: deque[tuple[str, str]] = deque(maxlen=5)
        self._speech_lock = threading.Lock()

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
            self._load_session(mode, session_id)

    def _load_session(self, mode: str, session_id: int | None) -> None:
        """Load session based on mode.

        Modes:
          - "auto": restore latest chat session if < 24h old (default, backward compat)
          - "blank": start a completely new chat, no session loaded
          - "resume": explicitly load the latest non-greeting session
          - "greeting": load the greeting session (reply context)
          - "session": load a specific session by ID (for history)
        """
        if mode == "blank":
            return  # fresh chat, no session loaded

        if mode == "session" and session_id is not None:
            self._session_id = session_id
            restored = self._repository.get_session_messages(str(session_id), limit=10)
            if restored:
                with self._messages_lock:
                    self._messages = deque(({"role": m["role"], "text": m["text"]} for m in restored), maxlen=50)
                    self._status_detail = "SESSION LOADED"
                    self._resumed_until = time.time() + 2.0
                    self._set_resume_context(restored)
            return

        if mode == "greeting":
            greeting = self._repository.get_greeting_session()
            if greeting:
                self._session_id = int(greeting["id"])
                restored = self._repository.get_session_messages(str(self._session_id), limit=10)
                if restored:
                    with self._messages_lock:
                        self._messages = deque(({"role": m["role"], "text": m["text"]} for m in restored), maxlen=50)
                        self._status_detail = "GREETING"
                        self._resumed_until = time.time() + 2.0
                        # Build pages from greeting text for nice display
                        last_msg = restored[-1]
                        if last_msg["role"] == "assistant":
                            self._build_pages(last_msg["text"])
            return

        # "auto" or "resume" — load latest chat session
        latest = self._repository.get_latest_chat_session()
        if latest:
            age_seconds = time.time() - float(latest.get("updated_at", latest.get("created_at", 0.0)))
            max_age = 24 * 3600 if mode == "auto" else float("inf")
            if age_seconds <= max_age:
                self._session_id = int(latest["id"])
                restored = self._repository.get_session_messages(str(self._session_id), limit=10)
                if restored:
                    with self._messages_lock:
                        self._messages = deque(({"role": m["role"], "text": m["text"]} for m in restored), maxlen=50)
                        self._status_detail = "SESSION RESTORED"
                        self._resumed_until = time.time() + 2.0
                        self._scroll_offset = 0
                    if mode == "resume":
                        self._set_resume_context(restored)

    def _set_resume_context(self, messages: list[dict]) -> None:
        """Set a context header from the last assistant message when resuming."""
        # Find last assistant message for context banner
        for msg in reversed(messages):
            if msg["role"] == "assistant":
                text = msg["text"].strip()
                # Take first sentence or first 60 chars
                first_sentence = text.split(".")[0] if "." in text[:60] else text[:60]
                if len(first_sentence) > 55:
                    first_sentence = first_sentence[:52] + "..."
                self._context_header = f"last: {first_sentence}"
                # Build pages from the full conversation for browsing
                last_msg = messages[-1]
                if last_msg["role"] == "assistant":
                    self._build_pages(last_msg["text"])
                break

    def update(self, dt: float):
        self._cursor_anim.update(dt)
        self._speaking_overlay.tick(int(dt * 1000))
        # Clear "TAP AGAIN TO RECORD" hint after confirmation window expires
        if self._confirm_tap_until and time.time() >= self._confirm_tap_until:
            self._confirm_tap_until = 0.0
            with self._messages_lock:
                if self._status_detail == "TAP AGAIN TO RECORD":
                    self._status_detail = ""
        # Check if hold has crossed the quick-talk threshold (600ms)
        if self._hold_timer is not None and self._mode == ChatMode.IDLE:
            if time.time() - self._hold_timer >= 0.6:
                self._hold_timer = None
                self._quick_talk = True
                self._start_recording()

        # Tick user typewriter (sent message animation)
        if self._user_typewriter and not self._user_typewriter.finished:
            self._user_typewriter.update(dt)
        elif self._user_typewriter and self._user_typewriter.finished:
            self._user_typewriter = None

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

        # Tick page typewriter
        if self._page_typewriter and not self._page_typewriter.finished:
            self._page_typewriter.update(dt)
        elif self._page_typewriter and self._page_typewriter.finished:
            if self._current_page < len(self._page_revealed):
                self._page_revealed[self._current_page] = True
            self._page_typewriter = None

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

    # Duration of the "tap again to record" confirmation window
    _CONFIRM_TAP_S = 1.5
    # Cooldown after TTS skip to absorb stray taps
    _POST_SPEAKING_COOLDOWN_S = 0.8

    def _handle_idle(self, action: str):
        if action == "SHORT_PRESS":
            if self._hold_timer is not None:
                # Hold timer active — this tap came from a short hold, ignore
                self._hold_timer = None
                return
            now = time.time()
            # Absorb stray taps right after skipping TTS
            if now < self._post_speaking_until:
                return
            if now < self._confirm_tap_until:
                # Second tap within confirmation window → start recording
                self._confirm_tap_until = 0.0
                self._quick_talk = False
                self._start_recording()
            else:
                # First tap → show confirmation hint, wait for second tap
                self._confirm_tap_until = now + self._CONFIRM_TAP_S
                with self._messages_lock:
                    self._status_detail = "TAP AGAIN TO RECORD"
        elif action == "DOUBLE_PRESS":
            self._confirm_tap_until = 0.0
            self._mode = ChatMode.ACTIONS
            self._action_template_index = 0
        elif action == "TRIPLE_PRESS":
            self._confirm_tap_until = 0.0
            if len(self._pages) > 1:
                # Mark current page as revealed
                if self._current_page < len(self._page_revealed):
                    self._page_revealed[self._current_page] = True
                self._page_typewriter = None
                # Cycle to next page
                self._current_page = (self._current_page + 1) % len(self._pages)
                # Track that user manually navigated (disables auto-scroll during streaming)
                self._user_browsing = True
                self._start_page_typewriter()

    # Grace period: tap within this many seconds to cancel instead of send
    _RECORDING_GRACE_S = 1.5

    def _handle_recording(self, action: str):
        if action == "SHORT_PRESS" and not self._quick_talk:
            elapsed = time.time() - self._recording_start_time
            if elapsed < self._RECORDING_GRACE_S:
                # Too soon — cancel recording instead of sending
                logger.info("recording_quick_cancel: elapsed=%.1fs < grace=%.1fs", elapsed, self._RECORDING_GRACE_S)
                self._recording_cancelled = True
                self._voice_stop_event.set()
            else:
                # Field recording: tap again → stop and send
                self._voice_stop_event.set()
        elif action == "LONG_PRESS":
            # Cancel recording (either mode)
            self._recording_cancelled = True
            self._voice_stop_event.set()

    def _action_items(self) -> list[dict]:
        """Action menu: templates + navigation items."""
        return list(self._templates) + [
            {"label": "SETTINGS", "message": ""},
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
            if selected["label"] == "SETTINGS":
                self._mode = ChatMode.IDLE
                if self._on_settings:
                    self._on_settings()
            elif selected["label"] == "BACK":
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
        result = self._speaking_overlay.handle_action(action)
        if result == "skip":
            # Stop current TTS immediately and clear the queue
            with self._speech_lock:
                self._speech_queue.clear()
            if self._audio_pipeline:
                self._audio_pipeline.stop_speaking()
            self._speaking_overlay.dismiss()
            self._mode = ChatMode.IDLE
            self._post_speaking_until = time.time() + self._POST_SPEAKING_COOLDOWN_S
            with self._messages_lock:
                self._status_detail = ""
        elif result == "next":
            # Advance to next page visually; stop TTS
            if self._audio_pipeline:
                self._audio_pipeline.stop_speaking()
            if len(self._pages) > 1:
                if self._current_page < len(self._page_revealed):
                    self._page_revealed[self._current_page] = True
                self._page_typewriter = None
                self._current_page = (self._current_page + 1) % len(self._pages)
                self._user_browsing = True
                self._start_page_typewriter()
            # Stay in SPEAKING mode if there are queued utterances,
            # otherwise go to IDLE
            with self._speech_lock:
                if not self._speech_queue:
                    self._speaking_overlay.dismiss()
                    self._mode = ChatMode.IDLE
                    self._post_speaking_until = time.time() + self._POST_SPEAKING_COOLDOWN_S
                    with self._messages_lock:
                        self._status_detail = ""
        elif result == "reply":
            # Stop TTS, clear queue, start recording
            with self._speech_lock:
                self._speech_queue.clear()
            if self._audio_pipeline:
                self._audio_pipeline.stop_speaking()
            self._speaking_overlay.dismiss()
            self._mode = ChatMode.IDLE
            self._quick_talk = True
            self._start_recording()

    def _start_page_typewriter(self) -> None:
        """Start typewriter for current page if not yet revealed."""
        if not self._pages or self._current_page >= len(self._pages):
            self._page_typewriter = None
            return
        if self._current_page < len(self._page_revealed) and self._page_revealed[self._current_page]:
            self._page_typewriter = None
            return
        page_text = "\n".join(self._pages[self._current_page])
        speed = "slow"
        if self._repository:
            saved_speed = self._repository.get_setting("text_speed", None)
            if saved_speed:
                speed = str(saved_speed)
        if speed == "custom" and self._repository:
            config_raw = self._repository.get_setting("typewriter_config", "{}")
            config = TypewriterConfig.from_json(str(config_raw))
            self._page_typewriter = TypewriterRenderer(page_text, config=config)
        else:
            self._page_typewriter = TypewriterRenderer(page_text, speed=speed)

    def _build_pages(self, response_text: str, user_message: str = "") -> None:
        """Split response into paginated pages and start typewriter on page 1.

        During streaming, this may be called multiple times as text grows.
        We preserve the user's browsing position if they manually navigated,
        otherwise auto-advance to the last page so the latest text is visible.
        """
        # Context header: truncated user message
        if user_message:
            truncated = user_message[:35]
            if len(user_message) > 35:
                truncated += "..."
            self._context_header = f"> {truncated}"
        elif not self._context_header:
            self._context_header = ""

        # Calculate available lines per page
        header_lines = 1 if self._context_header else 0
        hint_px = 14  # compact hint line
        available_h = PHYSICAL_H - (SAFE_INSET + STATUS_BAR_H + 2) - SAFE_INSET - hint_px
        lines_per_page = max(1, int(available_h / self._line_height) - header_lines - 1)  # -1 for page indicator

        # Word-wrap full response
        wrapped = self._wrap_text(response_text, PHYSICAL_W - SAFE_INSET * 2)

        # Split into pages
        old_page_count = len(self._pages)
        old_current = self._current_page
        new_pages = self._split_into_pages(wrapped, lines_per_page)
        new_page_count = len(new_pages)

        # Preserve revealed state for pages that haven't changed
        old_revealed = list(self._page_revealed)
        new_revealed = [False] * new_page_count
        for i in range(min(len(old_revealed), new_page_count)):
            new_revealed[i] = old_revealed[i]

        self._pages = new_pages
        self._page_revealed = new_revealed

        if self._is_streaming and old_page_count > 0:
            # During streaming: auto-advance to last page unless user is browsing
            if self._user_browsing:
                # Keep user on their chosen page (clamped to valid range)
                self._current_page = min(old_current, new_page_count - 1)
                # Don't touch the page typewriter for the page they're viewing
            else:
                # Auto-advance to the last page where new content appears
                last_page = new_page_count - 1
                if last_page != old_current or self._page_typewriter is None:
                    self._current_page = last_page
                    # Mark all pages before the last as revealed (skip typewriter for them)
                    for i in range(last_page):
                        self._page_revealed[i] = True
                    # Start typewriter on the new last page
                    self._page_typewriter = None
                    self._page_revealed[last_page] = False
                    self._start_page_typewriter()
                # else: same page, let existing typewriter continue
        else:
            # Initial build (not streaming, or first call): start from page 0
            self._current_page = 0
            self._user_browsing = False
            self._page_typewriter = None
            self._start_page_typewriter()

    def _get_action_bar_content(self) -> list[tuple[str, str]]:
        """Return action bar items for the current mode."""
        if self._mode == ChatMode.IDLE:
            if self._confirm_tap_until and time.time() < self._confirm_tap_until:
                return [("tap", "confirm rec"), ("hold", "talk")]
            items = [("tap", "rec"), ("hold", "talk"), ("double", "act")]
            if len(self._pages) > 1:
                items.append(("triple", "next"))
            return items
        elif self._mode == ChatMode.RECORDING:
            if self._quick_talk:
                return [("hold", "release")]
            elapsed = time.time() - self._recording_start_time
            if elapsed < self._RECORDING_GRACE_S:
                return [("tap", "cancel"), ("hold", "cancel")]
            return [("tap", "send"), ("hold", "cancel")]
        elif self._mode == ChatMode.ACTIONS:
            return [("tap", "next"), ("double", "select"), ("hold", "back")]
        elif self._mode == ChatMode.SPEAKING:
            items = [("double", "skip"), ("hold", "reply")]
            if len(self._pages) > 1:
                items.insert(1, ("triple", "next"))
            return items
        return []  # STREAMING — render plain text instead

    @staticmethod
    def _split_into_pages(lines: list[str], lines_per_page: int, max_pages: int = 4) -> list[list[str]]:
        """Split wrapped lines into pages, preferring paragraph boundaries."""
        return _shared_split_into_pages(lines, lines_per_page, max_pages)

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # ── Status bar (20px) ──
        pygame.draw.line(surface, HAIRLINE, (0, SAFE_INSET + STATUS_BAR_H - 1), (PHYSICAL_W, SAFE_INSET + STATUS_BAR_H - 1))
        header_text = self._font_small.render("CHAT", False, WHITE)
        surface.blit(header_text, (SAFE_INSET, SAFE_INSET + (STATUS_BAR_H - header_text.get_height()) // 2))

        # Recording indicator or connection status
        if self._mode == ChatMode.RECORDING:
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
        hint_px = 14
        msg_area_top = SAFE_INSET + STATUS_BAR_H + 2
        msg_area_bottom = PHYSICAL_H - SAFE_INSET - hint_px

        # ── Content area ──
        if self._pages:
            self._render_paginated(surface, msg_area_top, msg_area_bottom)
        else:
            self._render_conversation(surface, msg_area_top, msg_area_bottom)

        # ── Streaming indicator ──
        if self._is_streaming:
            dots = "." * ((pygame.time.get_ticks() // 400) % 4)
            indicator = self._font_small.render(dots, False, DIM3)
            surface.blit(indicator, (SAFE_INSET, msg_area_bottom - 14))

        # ── Overlays (on top of page content) ──
        if self._mode == ChatMode.ACTIONS:
            overlay_h = self._ACTION_ROW_H * 3 + 4
            overlay_top = msg_area_bottom - overlay_h
            pygame.draw.rect(surface, BLACK, (0, overlay_top, PHYSICAL_W, overlay_h + hint_px + SAFE_INSET))
            pygame.draw.line(surface, HAIRLINE, (0, overlay_top), (PHYSICAL_W, overlay_top))
            self._render_actions_submenu(surface, overlay_top + 2)
        elif self._mode == ChatMode.RECORDING:
            overlay_top = msg_area_bottom - self._ACTION_ROW_H
            pygame.draw.rect(surface, BLACK, (0, overlay_top, PHYSICAL_W, self._ACTION_ROW_H + hint_px + SAFE_INSET))
            elapsed = int(time.time() - self._recording_start_time)
            rec_surf = self._font.render(f"RECORDING  {elapsed}s", False, WHITE)
            surface.blit(rec_surf, (SAFE_INSET, overlay_top + 2))
        elif self._voice_step and self._voice_step not in ("", "SENDING"):
            overlay_h = self._ACTION_ROW_H * 3
            overlay_top = msg_area_bottom - overlay_h
            pygame.draw.rect(surface, BLACK, (0, overlay_top, PHYSICAL_W, overlay_h + hint_px + SAFE_INSET))
            self._render_voice_callout(surface, overlay_top)

        # ── Hint line (compact, always visible) ──
        hint_y = PHYSICAL_H - SAFE_INSET - hint_px
        bar_center_y = hint_y + hint_px // 2
        bar_content = self._get_action_bar_content()
        if bar_content:
            self._render_hint_line(surface, bar_center_y, bar_content)
        else:
            step_label = self._voice_step.lower() if self._voice_step else "thinking"
            stream_text = self._font_small.render(f"{step_label}...", False, DIM3)
            surface.blit(stream_text, ((PHYSICAL_W - stream_text.get_width()) // 2, bar_center_y - stream_text.get_height() // 2))

        # Speaking overlay (rendered on top of everything)
        if self._speaking_overlay.active:
            self._speaking_overlay.render(surface, tokens_module)

    # Markdown style → color mapping
    _MD_COLORS = {
        STYLE_BOLD: WHITE,
        STYLE_ITALIC: DIM3,
        STYLE_CODE: DIM2,
        STYLE_HEADER: WHITE,
        STYLE_BULLET: DIM1,
        "normal": WHITE,
    }

    def _render_styled_line(self, surface: pygame.Surface, line_text: str, x: int, y: int) -> None:
        """Render a line with markdown styling (bold=bright, italic=dim, code=dimmer)."""
        segments = parse_line(line_text)
        cx = x
        for seg in segments:
            color = self._MD_COLORS.get(seg.style, WHITE)
            font = self._font
            seg_surf = font.render(seg.text, False, color)
            surface.blit(seg_surf, (cx, y))
            cx += seg_surf.get_width()

    def _render_paginated(self, surface: pygame.Surface, top: int, bottom: int) -> None:
        """Render current page with context header and page indicator.

        During typewriter reveal, we render the page's pre-wrapped lines but
        truncate to the number of characters revealed so far. This avoids
        re-wrapping partial text (which causes line count mismatches and visual
        jumps as words complete).
        """
        y = top

        # Context header (1 line, dimmed)
        if self._context_header:
            header_surf = self._font_small.render(self._context_header, False, DIM2)
            surface.blit(header_surf, (SAFE_INSET, y))
            y += self._line_height

        # Page text — use pre-wrapped lines from pagination
        if self._current_page >= len(self._pages):
            page = []
        else:
            page = self._pages[self._current_page]

        # Determine how many characters to show (typewriter reveal)
        if self._page_typewriter and not self._page_typewriter.finished:
            visible_text = self._page_typewriter.get_visible_text()
            chars_to_show = len(visible_text)
        else:
            chars_to_show = -1  # show all

        chars_shown = 0
        for line_text in page:
            if y + self._line_height > bottom - self._line_height:
                break

            if chars_to_show < 0:
                # Fully revealed — render the whole line
                self._render_styled_line(surface, line_text, SAFE_INSET, y)
            else:
                # Count characters in this line (plus newline separator)
                line_len = len(line_text)
                remaining = chars_to_show - chars_shown
                if remaining <= 0:
                    break  # haven't revealed this line yet
                if remaining >= line_len:
                    # Full line revealed
                    self._render_styled_line(surface, line_text, SAFE_INSET, y)
                else:
                    # Partial line — truncate and render
                    partial = line_text[:remaining]
                    self._render_styled_line(surface, partial, SAFE_INSET, y)
                # +1 for the newline that joins lines in the typewriter text
                chars_shown += line_len + 1

            y += self._line_height

        # Page indicator (centered, small font, DIM1) — only if 2+ pages
        if len(self._pages) > 1:
            indicator = f"{self._current_page + 1}/{len(self._pages)}"
            ind_surf = self._font_small.render(indicator, False, DIM1)
            ind_x = (PHYSICAL_W - ind_surf.get_width()) // 2
            surface.blit(ind_surf, (ind_x, bottom - self._line_height))

    def _render_conversation(self, surface: pygame.Surface, top: int, bottom: int) -> None:
        """Render full conversation history (non-paginated fallback)."""
        with self._messages_lock:
            snapshot = list(self._messages)

        if self._typewriter and snapshot and snapshot[-1]["role"] == "assistant":
            snapshot = list(snapshot)
            snapshot[-1] = {"role": "assistant", "text": self._typewriter.get_visible_text()}

        # User message typewriter: show partially revealed text for latest user message
        if self._user_typewriter and snapshot:
            # Find the last user message and replace with typewriter text
            snapshot = list(snapshot)
            for i in range(len(snapshot) - 1, -1, -1):
                if snapshot[i]["role"] == "user":
                    snapshot[i] = {"role": "user", "text": self._user_typewriter.get_visible_text()}
                    break

        visible_lines = []  # list of (line_text, role)
        avail_w = PHYSICAL_W - SAFE_INSET * 2
        for msg in snapshot:
            if msg["role"] == "user":
                prefix = "> "
                lines = self._wrap_text(prefix + msg["text"], avail_w)
                for line in lines:
                    visible_lines.append((line, "user"))
            else:
                # Assistant: markdown-aware wrap preserving markers
                lines = wrap_markdown_text(msg["text"], self._font, avail_w)
                for line in lines:
                    visible_lines.append((line, "assistant"))
            # Paragraph spacing between messages
            visible_lines.append(("", "spacer"))

        # Remove trailing spacer
        if visible_lines and visible_lines[-1][1] == "spacer":
            visible_lines.pop()

        msg_y = top
        max_visible = int((bottom - top) / self._line_height)
        start = max(0, len(visible_lines) - max_visible - self._scroll_offset)
        for line_text, role in visible_lines[start:]:
            if msg_y > bottom:
                break
            if role == "spacer":
                # Half-height paragraph gap
                msg_y += self._line_height // 2
                continue
            if role == "assistant":
                self._render_styled_line(surface, line_text, SAFE_INSET, msg_y)
            else:
                # User messages: dim, no markdown parsing
                text_surface = self._font.render(line_text, False, DIM2)
                surface.blit(text_surface, (SAFE_INSET, msg_y))
            msg_y += self._line_height

        # Retry hint
        if not self._is_streaming and self._can_retry():
            hint = self._font_small.render("DBL: retry", False, DIM1)
            surface.blit(hint, (SAFE_INSET, bottom - 14))

        # Queue status
        queue_status = self._queue_status_copy()
        if queue_status:
            queue_surface = self._font_small.render(queue_status, False, DIM2)
            queue_x = max(96, PHYSICAL_W - queue_surface.get_width() - SAFE_INSET)
            surface.blit(queue_surface, (queue_x, bottom - 14))

    def _render_hint_line(self, surface: pygame.Surface, center_y: int, items: list[tuple[str, str]]) -> None:
        """Render compact gesture hint line at bottom."""
        rendered = []
        for icon_type, label in items:
            label_surf = self._font_small.render(label, False, DIM1)
            rendered.append((icon_type, label_surf))

        total_w = sum(8 + 2 + s.get_width() for _, s in rendered)
        spacing = max(4, (PHYSICAL_W - total_w) // (len(rendered) + 1))
        bx = spacing
        for icon_type, label_surf in rendered:
            ic = (bx + 3, center_y)
            if icon_type == "tap":
                pygame.draw.circle(surface, DIM1, ic, 2, 1)
            elif icon_type == "double":
                pygame.draw.circle(surface, DIM1, ic, 2, 1)
                pygame.draw.circle(surface, DIM1, ic, 1, 1)
            elif icon_type == "hold":
                pygame.draw.circle(surface, DIM1, ic, 2, 0)
            elif icon_type == "triple":
                for offset in (-3, 0, 3):
                    pygame.draw.circle(surface, DIM1, (ic[0] + offset, ic[1]), 2, 1)
            surface.blit(label_surf, (bx + 8, center_y - label_surf.get_height() // 2))
            bx += 8 + label_surf.get_width() + spacing

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
        is_transcribed = step == "TRANSCRIBED"

        # Step label (large)
        if is_transcribed:
            # Show a checkmark header for successful transcription
            step_color = (100, 255, 100)
            step_surf = self._font.render("HEARD:", False, step_color)
        else:
            step_color = (255, 80, 80) if is_error else WHITE
            step_surf = self._font.render(step, False, step_color)
        surface.blit(step_surf, (SAFE_INSET, top_y + 2))

        # Detail text (smaller, below step) — transcription preview or error
        if is_transcribed and error:
            # Show transcribed text as detail (error field carries the text)
            detail_surf = self._font_small.render(error[:32], False, WHITE)
            surface.blit(detail_surf, (SAFE_INSET, top_y + self._ACTION_ROW_H + 2))
        elif error and error != step:
            err_surf = self._font_small.render(error[:28], False, DIM2)
            surface.blit(err_surf, (SAFE_INSET, top_y + self._ACTION_ROW_H + 2))

        # Pipeline progress dots: REC → VAL → API → STT → SEND
        stages = ["REC", "VAL", "API", "STT", "SEND"]
        stage_map = {
            "RECORDING": 0, "STOPPING": 0,
            "VALIDATING": 1,
            "PREFLIGHT": 2,
            "TRANSCRIBING": 3,
            "TRANSCRIBED": 3,
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
        # Clear any stale voice step (e.g., ERROR from previous attempt)
        self._voice_step = ""

        # Run health check on first recording attempt
        if not self._health_checked:
            self._health_checked = True
            self._health.check_all_async()

        self._mode = ChatMode.RECORDING
        self._recording_cancelled = False
        self._voice_stop_event.clear()
        self._recording_start_time = time.time()
        if self._led:
            self._led.recording()
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

            # ── Step 4b: Energy check — skip STT if recording is mostly silence ──
            if not self._audio_has_energy(audio_path):
                logger.info("audio_silence_detected: skipping STT")
                self._set_voice_step("ERROR", "silence — tap closer")
                self._mode = ChatMode.IDLE
                if self._led:
                    self._led.off()
                return

            # ── Step 5: Transcribe (stay in RECORDING mode so user sees status) ──
            self._set_voice_step("TRANSCRIBING")
            if self._led:
                self._led.sending()
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

        # ── Step 5: Show transcription result briefly before sending ──
        self._set_voice_step("SENDING", text[:60])
        time.sleep(0.5)  # brief pause — user text typewriter provides the visual feedback

        # ── Step 6: Send to backend ──
        if self._led:
            self._led.sending()
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

    # Minimum RMS energy threshold for speech detection (16-bit PCM).
    # Typical silence sits around 50-200 RMS; speech usually exceeds 500.
    _MIN_AUDIO_RMS = 300

    @classmethod
    def _audio_has_energy(cls, audio_path: str) -> bool:
        """Return True if the WAV file contains enough energy to be speech."""
        import struct
        import wave

        try:
            with wave.open(audio_path, "rb") as wf:
                n_frames = wf.getnframes()
                if n_frames == 0:
                    return False
                sampwidth = wf.getsampwidth()
                channels = wf.getnchannels()
                raw = wf.readframes(n_frames)

            if sampwidth != 2:
                # Can't easily check non-16-bit; assume it has energy
                return True

            samples = struct.unpack(f"<{len(raw) // 2}h", raw)
            # If stereo, take every other sample (left channel) for speed
            if channels > 1:
                samples = samples[::channels]

            if not samples:
                return False

            # RMS energy
            sum_sq = sum(s * s for s in samples)
            rms = (sum_sq / len(samples)) ** 0.5
            logger.info("audio_energy_check: rms=%.1f threshold=%d frames=%d",
                        rms, cls._MIN_AUDIO_RMS, n_frames)
            return rms >= cls._MIN_AUDIO_RMS
        except Exception as exc:
            logger.warning("audio_energy_check_failed: %s — assuming has energy", exc)
            return True  # on error, don't block the pipeline

    def _send_message(self):
        text = self._input_text.strip()
        if not text:
            return

        # Stop any ongoing TTS and clear the speech queue
        if self._audio_pipeline and self._audio_pipeline.is_speaking():
            self._audio_pipeline.stop_speaking()
        with self._speech_lock:
            self._speech_queue.clear()
        self._speaking_overlay.dismiss()

        self._mode = ChatMode.STREAMING

        # Start user text typewriter animation (fast — just enough for visual feedback)
        self._user_typewriter = TypewriterRenderer(text, speed="fast")

        with self._messages_lock:
            self._messages.append({"role": "user", "text": text})

        if self._repository:
            if self._session_id is None:
                self._session_id = self._repository.create_session(title=text[:24])
            self._repository.add_message(self._session_id, "user", text)

        self._input_text = ""
        self._is_streaming = True
        self._scroll_offset = 0
        # Clear pagination
        self._pages = []
        self._current_page = 0
        self._page_revealed = []
        self._page_typewriter = None
        self._context_header = ""
        self._user_browsing = False
        self._status = self.STATUS_CONNECTED
        self._status_detail = ""
        self._last_failed_message = None
        self._last_error_retryable = False

        if self._led:
            self._led.responding()
        thread = threading.Thread(target=self._stream_response, args=(text,), daemon=True)
        thread.start()

    def send_message(self, text: str) -> None:
        """Public API: set input text and send immediately."""
        text = (text or "").strip()
        if not text:
            return
        self._input_text = text
        self._send_message()

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

            _last_page_build_len = 0
            for chunk in result:
                response_text += chunk
                with self._messages_lock:
                    self._messages[-1]["text"] = response_text

                # Progressive pagination: rebuild pages as text grows so new
                # pages appear and auto-scroll keeps up with incoming content.
                # First build at 80 chars, then every ~200 chars thereafter.
                text_len = len(response_text)
                if text_len >= 80 and (text_len - _last_page_build_len) >= 200 or (
                    _last_page_build_len == 0 and text_len >= 80
                ):
                    self._build_pages(response_text, user_message=message)
                    _last_page_build_len = text_len

            # Parse and apply inline commands (e.g. {{volume:80}})
            response_text = self._parse_commands(response_text)

            # Final page rebuild with complete text
            self._build_pages(response_text, user_message=message)

            if self._repository and self._session_id is not None:
                self._repository.add_message(self._session_id, "assistant", response_text)

            # TTS: determine voice mode (off/on/auto)
            voice_mode = "auto"
            if self._repository:
                voice_mode = str(self._repository.get_setting("voice_mode", "auto")).lower()

            # Agent-level voice toggle (from inline commands or default)
            agent_voice_enabled = bool(os.environ.get("SPEECHIFY_API_KEY"))
            if self._repository:
                stored = self._repository.get_setting("voice_enabled", None)
                if stored is not None:
                    agent_voice_enabled = str(stored).lower() in ("true", "1", "yes", "on")

            has_api_key = bool(os.environ.get("SPEECHIFY_API_KEY"))
            should_speak = _should_speak(voice_mode, agent_voice_enabled, has_api_key)
            logger.info("tts_check: voice_mode=%s agent_voice=%s has_key=%s -> speak=%s text_len=%d",
                        voice_mode, agent_voice_enabled, has_api_key, should_speak, len(response_text))

            # TTS only fires in active user-initiated chat sessions (not greetings/heartbeat)
            if self._audio_pipeline and response_text and should_speak:
                logger.info("tts_start: session=%s text_len=%d", self._session_id, len(response_text))
                self._speak_text(response_text)
            else:
                # No TTS — go straight to idle
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
            self._user_browsing = False  # reset so next response auto-scrolls
            if self._mode in (ChatMode.STREAMING, ChatMode.SPEAKING):
                self._mode = ChatMode.IDLE
            if self._led:
                if self._status == self.STATUS_CONNECTED:
                    self._led.success()
                # error cases already set led.error() via _mark_failed

    def _speak_text(self, text: str) -> None:
        """Play TTS for text. Queues if already speaking; only one utterance at a time."""
        with self._speech_lock:
            if self._audio_pipeline and self._audio_pipeline.is_speaking():
                # Already speaking — queue this utterance
                self._speech_queue.append((text, ""))
                logger.info("tts_queued: queue_depth=%d text_len=%d", len(self._speech_queue), len(text))
                return

        # Play immediately
        self._do_speak(text)

        # Drain the queue: play queued utterances one by one
        while True:
            with self._speech_lock:
                if not self._speech_queue:
                    break
                next_text, _ = self._speech_queue.popleft()
            # Check if we got cancelled between items
            if self._mode != ChatMode.SPEAKING:
                with self._speech_lock:
                    self._speech_queue.clear()
                break
            self._do_speak(next_text)

        # Done speaking — clean up
        self._speaking_overlay.dismiss()
        with self._messages_lock:
            self._status = self.STATUS_CONNECTED
            self._status_detail = ""
            self._voice_step = ""
            self._voice_error = ""
            self._last_failed_message = None
            self._last_error_retryable = False

    def _do_speak(self, text: str) -> None:
        """Execute a single TTS utterance (blocking)."""
        try:
            self._mode = ChatMode.SPEAKING
            self._speaking_overlay.show()
            with self._messages_lock:
                self._status_detail = "SPEAKING..."
            if self._led:
                self._led.speaking()
            self._audio_pipeline.speak(text)
        except Exception as tts_exc:
            logger.error("tts_failed: %s", tts_exc)

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

    # Regex for inline commands: {{command:value}}
    _CMD_RE = re.compile(r'\{\{(\w+):(\w+)\}\}')

    def _parse_commands(self, text: str) -> str:
        """Extract and execute inline commands from response text.

        Supported commands:
          {{volume:NUMBER}} — set device volume (0-100)
          {{voice:on}}      — enable TTS voice replies
          {{voice:off}}     — disable TTS voice replies

        Returns text with commands stripped out.
        """
        def _handle(match):
            cmd, val = match.group(1).lower(), match.group(2).lower()
            if cmd == "volume":
                try:
                    level = max(0, min(100, int(val)))
                    if self._repository:
                        self._repository.set_setting("volume", level)
                    logger.info("volume_set=%d via agent command", level)
                except (ValueError, TypeError):
                    pass
            elif cmd == "voice":
                voice_mode = "auto"
                if self._repository:
                    voice_mode = str(self._repository.get_setting("voice_mode", "auto")).lower()
                if voice_mode == "off":
                    logger.info("voice_command_ignored: voice_mode=off overrides agent")
                else:
                    enabled = val in ("on", "true", "1", "yes")
                    if self._repository:
                        self._repository.set_setting("voice_enabled", enabled)
                    logger.info("voice_enabled=%s via agent command", enabled)
            return ""  # strip command from display text

        return self._CMD_RE.sub(_handle, text).strip()

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
        return _shared_wrap_text(text, self._font, max_width)

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
