"""Messages panel backed by BlueBubbles server endpoints."""
from __future__ import annotations

import threading
import time

import pygame

from display.theme import load_ui_font, merge_runtime_ui_settings
from display.tokens import BLACK, DIM2, DIM3, PAD_WIDGET, PHYSICAL_H, PHYSICAL_W, ROW_H_MIN, STATUS_BAR_H, WHITE
from screens.base import BaseScreen


LIST_ROW_H = ROW_H_MIN
THREAD_ROW_H = ROW_H_MIN
THREAD_VISIBLE_ROWS = 5
HINT_MARGIN_BOTTOM = 1
CONTENT_TOP_PAD = 4
LIST_META_TOP_PAD = 2
LIST_SNIPPET_TOP_PAD = 13
LIST_UNREAD_DOT_X_PAD = 8
LIST_UNREAD_DOT_Y_PAD = 8
LIST_UNREAD_DOT_RADIUS = 2
CONFIRM_BOX_H = 80
CONFIRM_BOX_TOP_PAD = 8
CONFIRM_HINT_START_Y = 96
CONFIRM_BOX_BORDER = 3
CONFIRM_MAX_LINES = 6
CONFIRM_HINT_ROW_STEP = 13
TEXT_LINE_STEP = 12
THREAD_TEXT_MAX_CHARS = 36


class MessagesPanel(BaseScreen):
    STATE_LIST = "list"
    STATE_THREAD = "thread"
    STATE_DRAFT_VOICE = "draft_voice"
    STATE_CONFIRM_SEND = "confirm_send"

    def __init__(self, client, battery_pct: int = 84, audio_pipeline=None, led=None, on_back=None, ui_settings: dict | None = None):
        self._client = client
        self._battery_pct = battery_pct
        self._audio_pipeline = audio_pipeline
        self._led = led
        self._on_back = on_back
        self._ui_settings = merge_runtime_ui_settings(ui_settings)

        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)

        self._state = self.STATE_LIST
        self._loading = True
        self._focused_idx = 0
        self._thread_offset = 0
        self._conversations: list[dict] = []
        self._messages: list[dict] = []
        self._selected_chat_id = ""
        self._selected_title = ""
        self._draft_text = ""
        self._status_toast = ""
        self._status_toast_until = 0.0

        threading.Thread(target=self._load_conversations, daemon=True).start()

    def _load_conversations(self):
        self._conversations = self._client.get_conversations()
        self._loading = False

    def _load_thread(self, chat_id: str):
        self._messages = self._client.get_messages(chat_id)
        self._thread_offset = 0

    def handle_input(self, event: pygame.event.Event):
        _ = event

    def handle_action(self, action: str):
        if self._state == self.STATE_LIST:
            self._handle_list(action)
            return
        if self._state == self.STATE_THREAD:
            self._handle_thread(action)
            return
        if self._state == self.STATE_DRAFT_VOICE:
            self._handle_draft_voice(action)
            return
        if self._state == self.STATE_CONFIRM_SEND:
            self._handle_confirm(action)

    def _handle_list(self, action: str):
        if action == "DOUBLE_PRESS":
            if self._on_back:
                self._on_back()
            return
        if not self._conversations:
            return
        if action == "SHORT_PRESS":
            self._focused_idx = (self._focused_idx + 1) % len(self._conversations)
        elif action == "LONG_PRESS":
            selected = self._conversations[self._focused_idx]
            self._selected_chat_id = str(selected.get("chat_id", ""))
            self._selected_title = str(selected.get("title", "CONTACT"))
            self._load_thread(self._selected_chat_id)
            self._state = self.STATE_THREAD

    def _handle_thread(self, action: str):
        if action == "DOUBLE_PRESS":
            self._state = self.STATE_LIST
            return
        if action == "SHORT_PRESS":
            self._thread_offset = min(self._thread_offset + 1, max(0, len(self._messages) - 1))
        elif action == "LONG_PRESS":
            self._state = self.STATE_DRAFT_VOICE

    def _handle_draft_voice(self, action: str):
        if action == "DOUBLE_PRESS":
            self._state = self.STATE_THREAD
            return
        if action == "LONG_PRESS":
            self._capture_and_draft()

    def _handle_confirm(self, action: str):
        if action == "DOUBLE_PRESS":
            self._draft_text = ""
            self._state = self.STATE_THREAD
        elif action == "SHORT_PRESS":
            self._state = self.STATE_DRAFT_VOICE
        elif action == "LONG_PRESS":
            self._status_toast = "Sending..."
            if self._led:
                self._led.thinking()
            ok = self._client.send_message(self._selected_chat_id, self._draft_text, confirmed=True)
            self._status_toast = "Sent ✓" if ok else "Failed"
            if self._led:
                self._led.off() if ok else self._led.error()
            self._status_toast_until = time.time() + 1.5
            self._load_thread(self._selected_chat_id)
            self._state = self.STATE_THREAD

    def _capture_and_draft(self):
        if not self._audio_pipeline:
            return
        transcript = ""
        try:
            if self._led:
                self._led.listening()
            audio_path = self._audio_pipeline.record(max_seconds=30)
            stop_fn = getattr(self._audio_pipeline, "stop", None) or getattr(self._audio_pipeline, "stop_recording", None)
            if callable(stop_fn):
                stop_fn()
            transcript = self._audio_pipeline.transcribe(audio_path).strip()
        except Exception:
            transcript = ""
            if self._led:
                self._led.error()
        if self._led:
            self._led.off()
        if not transcript:
            return
        if self._led:
            self._led.thinking()
        draft = self._client.draft_reply(self._selected_chat_id, transcript)
        if self._led:
            self._led.off()
        self._draft_text = draft or transcript
        self._state = self.STATE_CONFIRM_SEND

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)
        if self._state == self.STATE_LIST:
            self._render_list(surface)
        elif self._state == self.STATE_THREAD:
            self._render_thread(surface)
        elif self._state == self.STATE_DRAFT_VOICE:
            self._render_draft_voice(surface)
        else:
            self._render_confirm(surface)

    def _render_status_bar(self, surface: pygame.Surface, title: str):
        pygame.draw.rect(surface, WHITE, pygame.Rect(0, 0, PHYSICAL_W, STATUS_BAR_H))
        label = self._font_small.render(f"● {title}  {self._battery_pct}%", False, BLACK)
        surface.blit(label, (PAD_WIDGET, (STATUS_BAR_H - label.get_height()) // 2))

    def _render_list(self, surface: pygame.Surface):
        self._render_status_bar(surface, "MESSAGES")
        content_y = STATUS_BAR_H + CONTENT_TOP_PAD
        if self._loading:
            txt = self._font_body.render("LOADING...", False, DIM2)
            surface.blit(txt, ((PHYSICAL_W - txt.get_width()) // 2, PHYSICAL_H // 2))
        elif not self._conversations:
            txt = self._font_body.render("NO MESSAGES", False, DIM2)
            surface.blit(txt, ((PHYSICAL_W - txt.get_width()) // 2, PHYSICAL_H // 2))
        else:
            row_h = LIST_ROW_H
            visible = (PHYSICAL_H - STATUS_BAR_H - STATUS_BAR_H) // row_h
            start = min(self._focused_idx, max(0, len(self._conversations) - visible))
            y = content_y
            for idx, convo in enumerate(self._conversations[start : start + visible]):
                actual = start + idx
                focused = actual == self._focused_idx
                if focused:
                    pygame.draw.rect(surface, WHITE, pygame.Rect(0, y, PHYSICAL_W, row_h))
                title = str(convo.get("title", "CONTACT"))[:16]
                ts = str(convo.get("timestamp", ""))[:6]
                unread = int(convo.get("unread", 0))
                color = BLACK if focused else WHITE
                meta_color = BLACK if focused else DIM2
                top = self._font_small.render(f"{title:<16}{ts}", False, color)
                surface.blit(top, (PAD_WIDGET, y + LIST_META_TOP_PAD))
                if unread > 0:
                    dot_color = BLACK if focused else WHITE
                    pygame.draw.circle(surface, dot_color, (PHYSICAL_W - LIST_UNREAD_DOT_X_PAD, y + LIST_UNREAD_DOT_Y_PAD), LIST_UNREAD_DOT_RADIUS)
                snippet = str(convo.get("snippet", ""))[:30]
                sub = self._font_small.render(snippet, False, meta_color)
                surface.blit(sub, (PAD_WIDGET, y + LIST_SNIPPET_TOP_PAD))
                y += row_h

        hint = self._font_hint.render("SHORT:↕  LONG:OPEN  DBL:BACK", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - HINT_MARGIN_BOTTOM))

    def _render_thread(self, surface: pygame.Surface):
        self._render_status_bar(surface, (self._selected_title or "CONTACT").upper()[:12])
        y = STATUS_BAR_H + CONTENT_TOP_PAD
        shown = self._messages[max(0, len(self._messages) - THREAD_VISIBLE_ROWS - self._thread_offset) : len(self._messages) - self._thread_offset]
        for message in shown:
            text = str(message.get("text", ""))[:THREAD_TEXT_MAX_CHARS]
            if bool(message.get("from_me", False)):
                line = self._font_small.render(text, False, WHITE)
                surface.blit(line, (PHYSICAL_W - line.get_width() - PAD_WIDGET, y + (THREAD_ROW_H - line.get_height()) // 2))
            else:
                line = self._font_small.render(text, False, WHITE)
                surface.blit(line, (PAD_WIDGET, y + (THREAD_ROW_H - line.get_height()) // 2))
            y += THREAD_ROW_H

        if self._status_toast and time.time() < self._status_toast_until:
            toast = self._font_small.render(self._status_toast, False, DIM2)
            surface.blit(toast, (PAD_WIDGET, PHYSICAL_H - ROW_H_MIN))

        hint = self._font_hint.render("SHORT:↕  LONG:REPLY  DBL:BACK", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - HINT_MARGIN_BOTTOM))

    def _render_draft_voice(self, surface: pygame.Surface):
        self._render_status_bar(surface, "REPLYING")
        y = PHYSICAL_H // 2 - ROW_H_MIN
        for row, color in [
            (f"TO: {self._selected_title[:16]}", WHITE),
            ("", WHITE),
            ("HOLD TO SPEAK", WHITE),
            ("your reply", DIM2),
            ("", WHITE),
            ("or type on companion app", DIM2),
        ]:
            if row:
                line = self._font_body.render(row, False, color)
                surface.blit(line, ((PHYSICAL_W - line.get_width()) // 2, y))
            y += TEXT_LINE_STEP

        hint = self._font_hint.render("LONG:▶ SPEAK  DBL:CANCEL", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - HINT_MARGIN_BOTTOM))

    def _render_confirm(self, surface: pygame.Surface):
        self._render_status_bar(surface, "DRAFT")
        self.render_confirm(surface)
        hint_rows = ["[SHORT]  REFINE", "[LONG ]  SEND ✓", "[DBL  ]  DISCARD"]
        y = STATUS_BAR_H + CONFIRM_HINT_START_Y
        for row in hint_rows:
            line = self._font_small.render(row, False, WHITE)
            surface.blit(line, ((PHYSICAL_W - line.get_width()) // 2, y))
            y += CONFIRM_HINT_ROW_STEP

        hint = self._font_hint.render("SHORT:REFINE  LONG:SEND  DBL:BACK", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - HINT_MARGIN_BOTTOM))

    def render_confirm(self, surface: pygame.Surface):
        x, y, w, h = PAD_WIDGET, STATUS_BAR_H + CONFIRM_BOX_TOP_PAD, PHYSICAL_W - (PAD_WIDGET * 2), CONFIRM_BOX_H
        pygame.draw.rect(surface, WHITE, pygame.Rect(x, y, w, h), width=CONFIRM_BOX_BORDER)
        lines = self._wrap_text(self._draft_text or "", w - (PAD_WIDGET * 2))
        if len(lines) > CONFIRM_MAX_LINES:
            lines = lines[:CONFIRM_MAX_LINES]
            lines[-1] = (lines[-1][: max(0, len(lines[-1]) - 3)] + "...") if lines[-1] else "..."
        yy = y + PAD_WIDGET
        for line in lines:
            s = self._font_small.render(line, False, WHITE)
            surface.blit(s, (x + PAD_WIDGET, yy))
            yy += TEXT_LINE_STEP

    def _wrap_text(self, text: str, max_width: int) -> list[str]:
        if not text:
            return [""]
        out: list[str] = []
        cur = ""
        for char in text:
            test = cur + char
            if self._font_small.size(test)[0] <= max_width:
                cur = test
            else:
                out.append(cur)
                cur = char
        if cur:
            out.append(cur)
        return out
