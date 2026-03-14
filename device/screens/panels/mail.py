"""Mail panel backed by Gmail adapter endpoints."""

from __future__ import annotations

import threading
import time

import pygame

from display.theme import load_ui_font, merge_runtime_ui_settings
from display.tokens import BLACK, DIM2, DIM3, PHYSICAL_H, PHYSICAL_W, STATUS_BAR_H, WHITE
from screens.base import BaseScreen


class MailPanel(BaseScreen):
    STATE_LIST = "list"
    STATE_THREAD = "thread"
    STATE_DRAFT_VOICE = "draft_voice"
    STATE_CONFIRM = "confirm"
    CONFIRM_HINT_ROWS = ["SHORT: REFINE", "LONG:  SAVE DRAFT ✓", "DBL:   DISCARD"]

    def __init__(self, client, battery_pct: int = 84, audio_pipeline=None, on_back=None, ui_settings: dict | None = None):
        self._client = client
        self._battery_pct = battery_pct
        self._audio_pipeline = audio_pipeline
        self._on_back = on_back
        self._ui_settings = merge_runtime_ui_settings(ui_settings)

        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._font_hint = load_ui_font("hint", self._ui_settings)

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
        self._threads = self._client.get_mail_inbox()
        self._loading = False

    def _load_thread(self, thread_id: str):
        self._messages = self._client.get_mail_thread(thread_id)
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
        if action == "DOUBLE_PRESS":
            if self._on_back:
                self._on_back()
            return
        if not self._threads:
            return
        if action == "SHORT_PRESS":
            self._focused_idx = (self._focused_idx + 1) % len(self._threads)
        elif action == "LONG_PRESS":
            selected = self._threads[self._focused_idx]
            self._selected_thread_id = str(selected.get("thread_id", ""))
            self._selected_sender = str(selected.get("sender", "CONTACT"))
            self._selected_subject = str(selected.get("subject", ""))
            self._load_thread(self._selected_thread_id)
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
            draft_id = self._client.create_mail_draft(self._selected_thread_id, self._draft_text, confirmed=True)
            self._status_toast = "Draft saved ✓" if draft_id else "Draft failed"
            self._status_toast_until = time.time() + 1.5
            self._state = self.STATE_THREAD

    def _capture_and_draft(self):
        if not self._audio_pipeline:
            return
        transcript = ""
        try:
            audio_path = self._audio_pipeline.record(max_seconds=30)
            stop_fn = getattr(self._audio_pipeline, "stop", None) or getattr(self._audio_pipeline, "stop_recording", None)
            if callable(stop_fn):
                stop_fn()
            transcript = self._audio_pipeline.transcribe(audio_path).strip()
        except Exception:
            transcript = ""

        if not transcript:
            return

        draft = self._client.draft_mail_reply(self._selected_thread_id, transcript)
        self._draft_text = draft or transcript
        self._state = self.STATE_CONFIRM

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
        label = self._font_small.render(f"● {title}  {self._battery_pct}%", False, WHITE)
        surface.blit(label, (6, (STATUS_BAR_H - label.get_height()) // 2))

    def _render_list(self, surface: pygame.Surface):
        self._render_status_bar(surface, "MAIL")
        content_y = STATUS_BAR_H + 4
        if self._loading:
            txt = self._font_body.render("LOADING...", False, DIM2)
            surface.blit(txt, ((PHYSICAL_W - txt.get_width()) // 2, PHYSICAL_H // 2))
        elif not self._threads:
            txt = self._font_body.render("INBOX EMPTY ✓", False, DIM2)
            surface.blit(txt, ((PHYSICAL_W - txt.get_width()) // 2, PHYSICAL_H // 2))
        else:
            row_h = 26
            visible = (PHYSICAL_H - STATUS_BAR_H - 18) // row_h
            start = min(self._focused_idx, max(0, len(self._threads) - visible))
            y = content_y
            for idx, thread in enumerate(self._threads[start : start + visible]):
                actual = start + idx
                focused = actual == self._focused_idx
                if focused:
                    pygame.draw.rect(surface, WHITE, pygame.Rect(0, y, PHYSICAL_W, row_h))

                sender = str(thread.get("sender", "SENDER"))[:14]
                ts = str(thread.get("timestamp", ""))[:8]
                unread_dot = "●" if bool(thread.get("unread")) else ""
                color = BLACK if focused else WHITE
                meta_color = BLACK if focused else DIM2
                top = self._font_small.render(f"{sender:<14}{ts:>8} {unread_dot}", False, color)
                surface.blit(top, (6, y + 2))
                subject = str(thread.get("subject", ""))[:28]
                sub = self._font_small.render(subject, False, meta_color)
                surface.blit(sub, (6, y + 13))
                y += row_h

        hint = self._font_hint.render("SHORT:↕  LONG:OPEN  DBL:BACK", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 1))

    def _render_thread(self, surface: pygame.Surface):
        self._render_status_bar(surface, self._selected_sender.upper()[:12] if self._selected_sender else "THREAD")
        subject = self._font_small.render(self._selected_subject[:32], False, DIM2)
        surface.blit(subject, (6, STATUS_BAR_H + 2))
        y = STATUS_BAR_H + 16
        shown = self._messages[max(0, len(self._messages) - 5 - self._thread_offset) : len(self._messages) - self._thread_offset]
        for message in shown:
            text = str(message.get("text", ""))[:34]
            if bool(message.get("from_me", False)):
                line = self._font_small.render(text, False, WHITE)
                surface.blit(line, (PHYSICAL_W - line.get_width() - 6, y))
                y += 14
            else:
                sender = self._font_small.render(str(message.get("sender", "Them"))[:14], False, DIM2)
                surface.blit(sender, (6, y))
                y += 10
                line = self._font_small.render(text, False, WHITE)
                surface.blit(line, (6, y))
                y += 14

        if self._status_toast and time.time() < self._status_toast_until:
            toast = self._font_small.render(self._status_toast, False, DIM2)
            surface.blit(toast, (6, PHYSICAL_H - 26))

        hint = self._font_hint.render("SHORT:↕  LONG:REPLY  DBL:BACK", False, DIM3)
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
        y = PHYSICAL_H // 2 - 38
        for row in rows:
            if row:
                color = DIM2 if row.startswith("RE:") else WHITE
                line = self._font_small.render(row, False, color)
                surface.blit(line, ((PHYSICAL_W - line.get_width()) // 2, y))
            y += 12

        hint = self._font_hint.render("LONG:▶ SPEAK  DBL:CANCEL", False, DIM3)
        surface.blit(hint, ((PHYSICAL_W - hint.get_width()) // 2, PHYSICAL_H - hint.get_height() - 1))

    def _render_confirm(self, surface: pygame.Surface):
        self._render_status_bar(surface, "DRAFT")
        header = self._font_small.render(f"REPLY TO: {self._selected_sender[:16]}", False, DIM2)
        surface.blit(header, (6, STATUS_BAR_H + 3))

        x, y, w, h = 6, STATUS_BAR_H + 16, PHYSICAL_W - 12, 80
        pygame.draw.rect(surface, WHITE, pygame.Rect(x, y, w, h), width=2)
        lines = self._wrap_text(self._draft_text, w - 10)[:5]
        yy = y + 5
        for line in lines:
            s = self._font_small.render(line, False, WHITE)
            surface.blit(s, (x + 5, yy))
            yy += 12

        hy = STATUS_BAR_H + 102
        for row in self.CONFIRM_HINT_ROWS:
            line = self._font_small.render(row, False, WHITE)
            surface.blit(line, ((PHYSICAL_W - line.get_width()) // 2, hy))
            hy += 13

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
