"""Mail panel backed by Gmail adapter endpoints."""

from __future__ import annotations

import threading
import time

import pygame

from display.text_utils import wrap_text
from display.theme import load_ui_font, merge_runtime_ui_settings
from display.tokens import BLACK, DIM2, DIM3, DIM4, HAIRLINE, PHYSICAL_H, PHYSICAL_W, ROW_H_MIN, STATUS_BAR_H, WHITE
from screens.base import BaseScreen


class MailPanel(BaseScreen):
    STATE_LIST = "list"
    STATE_THREAD = "thread"
    STATE_DRAFT_VOICE = "draft_voice"
    STATE_CONFIRM = "confirm"
    CONFIRM_HINT_ROWS = ["SHORT: REFINE", "DBL:   SAVE DRAFT \u2713", "LONG:  DISCARD"]

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

        self._lock = threading.Lock()
        self._state = self.STATE_LIST
        self._loading = True
        self._focused_idx = 0
        self._thread_offset = 0
        self._threads: list[dict] = []
        self._messages: list[dict] = []
        self._selected_thread_id = ""
        self._selected_sender = ""
        self._selected_subject = ""
        self._draft_text = ""
        self._status_toast = ""
        self._status_toast_until = 0.0

        threading.Thread(target=self._load_threads, daemon=True).start()

    def _load_threads(self):
        threads = self._client.get_mail_inbox()
        with self._lock:
            self._threads = threads
            self._loading = False

    def _load_thread(self, thread_id: str):
        msgs = self._client.get_mail_thread(thread_id)
        with self._lock:
            self._messages = msgs
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
        if self._state == self.STATE_CONFIRM:
            self._handle_confirm(action)

    def _handle_list(self, action: str):
        if action == "LONG_PRESS":
            if self._on_back:
                self._on_back()
            return
        with self._lock:
            if not self._threads:
                return
            if action == "SHORT_PRESS":
                self._focused_idx = (self._focused_idx + 1) % len(self._threads)
                return
            elif action == "TRIPLE_PRESS":
                self._focused_idx = (self._focused_idx - 1) % len(self._threads)
                return
            elif action == "DOUBLE_PRESS":
                selected = self._threads[self._focused_idx]
                self._selected_thread_id = str(selected.get("thread_id", ""))
                self._selected_sender = str(selected.get("sender", "CONTACT"))
                self._selected_subject = str(selected.get("subject", ""))
        if action == "DOUBLE_PRESS":
            self._load_thread(self._selected_thread_id)
            with self._lock:
                self._state = self.STATE_THREAD

    def _handle_thread(self, action: str):
        if action == "LONG_PRESS":
            self._state = self.STATE_LIST
            return
        with self._lock:
            if action == "SHORT_PRESS":
                self._thread_offset = min(self._thread_offset + 1, max(0, len(self._messages) - 1))
            elif action == "TRIPLE_PRESS":
                self._thread_offset = max(self._thread_offset - 1, 0)
            elif action == "DOUBLE_PRESS":
                self._state = self.STATE_DRAFT_VOICE

    def _handle_draft_voice(self, action: str):
        if action == "LONG_PRESS":
            self._state = self.STATE_THREAD
            return
        if action == "DOUBLE_PRESS":
            self._capture_and_draft()
        elif action == "SHORT_PRESS":
            return
        elif action == "TRIPLE_PRESS":
            return

    def _handle_confirm(self, action: str):
        if action == "LONG_PRESS":
            self._draft_text = ""
            self._state = self.STATE_THREAD
        elif action == "SHORT_PRESS":
            self._state = self.STATE_DRAFT_VOICE
        elif action == "DOUBLE_PRESS":
            if self._led:
                self._led.thinking()
            draft_id = self._client.create_mail_draft(self._selected_thread_id, self._draft_text, confirmed=True)
            if self._led:
                self._led.off() if draft_id else self._led.error()
            self._status_toast = "Draft saved \u2713" if draft_id else "Draft failed"
            self._status_toast_until = time.time() + 1.5
            self._state = self.STATE_THREAD
        elif action == "TRIPLE_PRESS":
            self._draft_text = ""
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
        draft = self._client.draft_mail_reply(self._selected_thread_id, transcript)
        if self._led:
            self._led.off()
        with self._lock:
            self._draft_text = draft or transcript
            self._state = self.STATE_CONFIRM

    def _render_skeleton(self, surface, y, count=4):
        from display.skeleton import render_skeleton
        render_skeleton(surface, y, count)

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
        from display.panel_status_bar import render_panel_status_bar
        render_panel_status_bar(surface, f"\u25cf {title}", self._font_small,
                                right_text=f"{self._battery_pct}%",
                                bg_color=BLACK, text_color=WHITE)

    def _render_list(self, surface: pygame.Surface):
        self._render_status_bar(surface, "MAIL")
        content_y = STATUS_BAR_H + 4
        with self._lock:
            loading = self._loading
            threads = list(self._threads)
            focused_idx = self._focused_idx
        if loading:
            self._render_skeleton(surface, content_y)
        elif not threads:
            txt = self._font_body.render("INBOX EMPTY \u2713", False, DIM2)
            surface.blit(txt, ((PHYSICAL_W - txt.get_width()) // 2, PHYSICAL_H // 2))
        else:
            row_h = ROW_H_MIN
            visible = (PHYSICAL_H - STATUS_BAR_H - 18) // row_h
            start = min(focused_idx, max(0, len(threads) - visible))
            y = content_y
            for idx, thread in enumerate(threads[start : start + visible]):
                actual = start + idx
                focused = actual == focused_idx
                if focused:
                    pygame.draw.rect(surface, WHITE, pygame.Rect(0, y, PHYSICAL_W, row_h))

                sender = str(thread.get("sender", "SENDER"))[:14]
                ts = str(thread.get("timestamp", ""))[:8]
                unread_dot = "\u25cf" if bool(thread.get("unread")) else ""
                color = BLACK if focused else WHITE
                meta_color = BLACK if focused else DIM2
                top = self._font_small.render(f"{sender:<14}{ts:>8} {unread_dot}", False, color)
                surface.blit(top, (6, y + 2))
                subject = str(thread.get("subject", ""))[:28]
                sub = self._font_small.render(subject, False, meta_color)
                surface.blit(sub, (6, y + self._font_small.get_height() + 4))
                y += row_h

        hint = self._font_hint.render("SHORT:\u2195  DBL:OPEN  LONG:BACK", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 1))

    def _render_thread(self, surface: pygame.Surface):
        self._render_status_bar(surface, self._selected_sender.upper()[:12] if self._selected_sender else "THREAD")
        subject = self._font_small.render(self._selected_subject[:32], False, DIM2)
        surface.blit(subject, (6, STATUS_BAR_H + 2))
        line_step = self._font_small.get_height() + 4
        y = STATUS_BAR_H + 16
        with self._lock:
            messages = list(self._messages)
            thread_offset = self._thread_offset
        shown = messages[max(0, len(messages) - 5 - thread_offset) : len(messages) - thread_offset]
        for message in shown:
            text = str(message.get("text", ""))[:34]
            if bool(message.get("from_me", False)):
                line = self._font_small.render(text, False, WHITE)
                surface.blit(line, (PHYSICAL_W - line.get_width() - 6, y))
                y += line_step
            else:
                sender = self._font_small.render(str(message.get("sender", "Them"))[:14], False, DIM2)
                surface.blit(sender, (6, y))
                y += line_step
                line = self._font_small.render(text, False, WHITE)
                surface.blit(line, (6, y))
                y += line_step

        if self._status_toast and time.time() < self._status_toast_until:
            toast = self._font_small.render(self._status_toast, False, DIM2)
            surface.blit(toast, (6, PHYSICAL_H - 26))

        hint = self._font_hint.render("SHORT:\u2195  DBL:REPLY  LONG:BACK", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 1))

    def _render_draft_voice(self, surface: pygame.Surface):
        self._render_status_bar(surface, "DRAFTING")
        rows = [
            "REPLY TO:",
            self._selected_sender[:20],
            f"RE: {self._selected_subject[:20]}",
            "",
            "HOLD TO SPEAK your reply",
            "",
            "Draft saved to Gmail",
        ]
        draft_line_step = self._font_small.get_height() + 4
        y = PHYSICAL_H // 2 - 38
        for row in rows:
            if row:
                color = DIM2 if row.startswith("RE:") else WHITE
                line = self._font_small.render(row, False, color)
                surface.blit(line, ((PHYSICAL_W - line.get_width()) // 2, y))
            y += draft_line_step

        hint = self._font_hint.render("DBL:\u25b6 SPEAK  LONG:CANCEL", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 1))

    def _render_confirm(self, surface: pygame.Surface):
        self._render_status_bar(surface, "DRAFT")
        header = self._font_small.render(f"REPLY TO: {self._selected_sender[:16]}", False, DIM2)
        surface.blit(header, (6, STATUS_BAR_H + 3))

        x, y, w, h = 6, STATUS_BAR_H + 16, PHYSICAL_W - 12, 80
        pygame.draw.rect(surface, WHITE, pygame.Rect(x, y, w, h), width=2)
        confirm_line_step = self._font_small.get_height() + 4
        lines = wrap_text(self._draft_text, w - 10, self._font_small)[:5]
        yy = y + 5
        for line in lines:
            s = self._font_small.render(line, False, WHITE)
            surface.blit(s, (x + 5, yy))
            yy += confirm_line_step

        hy = STATUS_BAR_H + 102
        for row in self.CONFIRM_HINT_ROWS:
            line = self._font_small.render(row, False, WHITE)
            surface.blit(line, ((PHYSICAL_W - line.get_width()) // 2, hy))
            hy += confirm_line_step

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
