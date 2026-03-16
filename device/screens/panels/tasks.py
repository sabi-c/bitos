"""Tasks panel backed by server /tasks/today with offline cache."""
from __future__ import annotations

import threading

import pygame

from screens.base import BaseScreen
from display.tokens import BLACK, WHITE, DIM2, DIM3, DIM4, HAIRLINE, PHYSICAL_W, PHYSICAL_H, STATUS_BAR_H, ROW_H_MIN
from display.theme import merge_runtime_ui_settings, load_ui_font


class TasksPanel(BaseScreen):
    def __init__(self, client, repository, on_back=None, ui_settings: dict | None = None):
        self._client = client
        self._repository = repository
        self._on_back = on_back
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._cursor = 0
        self._confirm_complete = False
        self._state = "loading"
        self._tasks: list[dict] = []
        self._load_thread: threading.Thread | None = None

    def on_enter(self):
        self._fetch_tasks()

    def _fetch_tasks(self):
        if self._load_thread and self._load_thread.is_alive():
            return

        def _run():
            try:
                tasks = self._client.get_tasks()
                if tasks:
                    self._tasks = tasks
                    self._state = "ready"
                    self._repository.cache_today_tasks(tasks)
                else:
                    self._tasks = self._repository.get_cached_today_tasks()
                    self._state = "empty" if not self._tasks else "offline"
            except Exception:
                self._tasks = self._repository.get_cached_today_tasks()
                self._state = "offline"

        self._state = "loading"
        self._load_thread = threading.Thread(target=_run, daemon=True)
        self._load_thread.start()

    def handle_input(self, event: pygame.event.Event):
        _ = event

    def handle_action(self, action: str):
        if action == "LONG_PRESS":
            if self._on_back:
                self._on_back()
            return
        if not self._tasks:
            return
        if action == "SHORT_PRESS":
            self._confirm_complete = False
            self._cursor = (self._cursor + 1) % len(self._tasks)
        elif action == "TRIPLE_PRESS":
            self._confirm_complete = False
            self._cursor = (self._cursor - 1) % len(self._tasks)
        elif action == "DOUBLE_PRESS":
            # VERIFIED: DOUBLE_PRESS first shows confirm hint, second DBL marks task complete in-place.
            if not self._confirm_complete:
                self._confirm_complete = True
                return
            self._tasks[self._cursor]["done"] = True
            self._confirm_complete = False

    def _render_skeleton(self, surface, y, count=4):
        """Render skeleton loading rows with step blink."""
        blink = (pygame.time.get_ticks() // 800) % 2 == 0
        color = DIM3 if blink else DIM4
        for _ in range(count):
            pygame.draw.rect(surface, color, (8, y + 4, PHYSICAL_W - 48, 8))
            pygame.draw.rect(surface, HAIRLINE, (PHYSICAL_W - 36, y + 4, 28, 8))
            pygame.draw.line(surface, HAIRLINE, (0, y + ROW_H_MIN - 1), (PHYSICAL_W, y + ROW_H_MIN - 1))
            y += ROW_H_MIN

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)
        title = self._font_small.render("TASKS", False, WHITE)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))

        if self._state == "loading":
            self._render_skeleton(surface, STATUS_BAR_H + 12)
            return
        if self._state == "empty":
            s = self._font_body.render("NO TASKS TODAY ✓", False, DIM2)
            surface.blit(s, ((PHYSICAL_W - s.get_width()) // 2, PHYSICAL_H // 2))
            return
        if self._state == "offline":
            s = self._font_small.render("OFFLINE — CACHED DATA", False, DIM3)
            surface.blit(s, ((PHYSICAL_W - s.get_width()) // 2, STATUS_BAR_H + 2))

        max_rows = max(1, (PHYSICAL_H - STATUS_BAR_H - 6) // ROW_H_MIN)
        start = min(self._cursor, max(0, len(self._tasks) - max_rows))
        y = STATUS_BAR_H + 12
        for idx, task in enumerate(self._tasks[start : start + max_rows]):
            actual = start + idx
            focused = actual == self._cursor
            if focused:
                pygame.draw.rect(surface, WHITE, pygame.Rect(0, y, PHYSICAL_W, ROW_H_MIN))
            color = BLACK if focused else WHITE
            indicator = "> " if focused else "- "
            project = str(task.get("project", "INBOX"))[:10]
            title_text = str(task.get("title", ""))[:24]
            surface.blit(self._font_small.render(indicator + project, False, color if focused else DIM2), (4, y + 2))
            surface.blit(self._font_body.render(title_text, False, color), (4, y + self._font_small.get_height() + 4))
            y += ROW_H_MIN

        if self._confirm_complete:
            hint = self._font_small.render("DBL AGAIN TO COMPLETE", False, DIM2)
            surface.blit(hint, (6, PHYSICAL_H - 16))
