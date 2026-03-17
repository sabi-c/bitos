"""Chat history panel — browse and open past chat sessions."""
from __future__ import annotations

import threading
import time

import pygame

from screens.base import BaseScreen
from display.tokens import BLACK, WHITE, DIM2, DIM3, PHYSICAL_W, PHYSICAL_H, STATUS_BAR_H
from display.theme import merge_runtime_ui_settings, load_ui_font


class ChatHistoryPanel(BaseScreen):
    """Scrollable list of past chat sessions. Select to open."""

    def __init__(self, repository, on_open_session, on_back=None, ui_settings: dict | None = None):
        self._repository = repository
        self._on_open_session = on_open_session
        self._on_back = on_back
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._lock = threading.Lock()
        self._cursor = 0
        self._sessions: list[dict] = []
        self._state = "loading"

    def on_enter(self):
        self._fetch_sessions()

    def _fetch_sessions(self):
        def _run():
            try:
                sessions = self._repository.list_sessions(limit=20)
                with self._lock:
                    self._sessions = sessions if sessions else []
                    self._state = "ready" if sessions else "empty"
            except Exception:
                with self._lock:
                    self._sessions = []
                    self._state = "error"

        self._state = "loading"
        threading.Thread(target=_run, daemon=True).start()

    def handle_input(self, event: pygame.event.Event):
        _ = event

    def handle_action(self, action: str):
        if action == "LONG_PRESS":
            if self._on_back:
                self._on_back()
            return

        with self._lock:
            if self._state != "ready" or not self._sessions:
                return

            if action == "SHORT_PRESS":
                self._cursor = (self._cursor + 1) % len(self._sessions)
            elif action == "TRIPLE_PRESS":
                self._cursor = (self._cursor - 1) % len(self._sessions)
            elif action == "DOUBLE_PRESS":
                session = self._sessions[self._cursor]
                if self._on_open_session and "id" in session:
                    self._on_open_session(session["id"])

    def update(self, dt: float):
        pass

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)
        w, h = surface.get_size()
        y_start = STATUS_BAR_H + 2
        row_h = self._font.get_height() + 6

        with self._lock:
            if self._state == "loading":
                msg = self._font_small.render("Loading...", False, DIM3)
                surface.blit(msg, (6, y_start + 10))
                return

            if self._state == "empty":
                msg = self._font_small.render("No chat history", False, DIM3)
                surface.blit(msg, (6, y_start + 10))
                return

            if self._state == "error":
                msg = self._font_small.render("Load error", False, DIM3)
                surface.blit(msg, (6, y_start + 10))
                return

            # Header
            header = self._font_small.render("CHAT HISTORY", False, DIM2)
            surface.blit(header, (4, y_start))
            y = y_start + header.get_height() + 4

            # Visible rows
            visible_rows = max(1, (h - y - 2) // row_h)
            # Scroll window so cursor is visible
            scroll_top = max(0, self._cursor - visible_rows + 1)

            for i in range(scroll_top, min(scroll_top + visible_rows, len(self._sessions))):
                session = self._sessions[i]
                selected = i == self._cursor

                if selected:
                    pygame.draw.rect(surface, WHITE, (0, y, w, row_h))
                    text_color = BLACK
                else:
                    text_color = DIM3

                # Title or fallback
                title = str(session.get("title") or "untitled")[:18]
                title_surf = self._font.render(title, False, text_color)
                surface.blit(title_surf, (4, y + 2))

                # Time ago (right-aligned)
                age_s = time.time() - float(session.get("updated_at", 0))
                if age_s < 3600:
                    age_str = f"{int(age_s / 60)}m"
                elif age_s < 86400:
                    age_str = f"{int(age_s / 3600)}h"
                else:
                    age_str = f"{int(age_s / 86400)}d"
                age_surf = self._font_small.render(age_str, False, text_color)
                surface.blit(age_surf, (w - age_surf.get_width() - 4, y + 3))

                y += row_h
