"""Agent subtasks panel — lists background LLM tasks with status and cost."""
from __future__ import annotations

import threading
import textwrap

import pygame

from screens.base import BaseScreen
from display.tokens import BLACK, WHITE, DIM2, DIM3, PHYSICAL_W, PHYSICAL_H, STATUS_BAR_H, ROW_H_MIN
from display.theme import merge_runtime_ui_settings, load_ui_font


_STATUS_ICON = {
    "pending": "...",
    "running": "\u27F3",
    "complete": "\u2713",
    "failed": "\u2717",
}


class AgentTasksPanel(BaseScreen):
    """Displays agent subtasks fetched from the backend."""

    def __init__(self, client, repository=None, on_back=None, ui_settings: dict | None = None):
        self._client = client
        self._repository = repository
        self._on_back = on_back
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._lock = threading.Lock()
        self._cursor = 0
        self._state = "loading"
        self._tasks: list[dict] = []
        self._expanded = False
        self._detail_page = 0
        self._detail_pages: list[list[str]] = []
        self._load_thread: threading.Thread | None = None

    def on_enter(self):
        self._fetch_tasks()

    def _fetch_tasks(self):
        if self._load_thread and self._load_thread.is_alive():
            return

        def _run():
            try:
                tasks = self._client.get_agent_subtasks()
                with self._lock:
                    self._tasks = tasks if tasks else []
                    self._state = "ready" if tasks else "empty"
            except Exception:
                with self._lock:
                    self._tasks = []
                    self._state = "empty"

        self._state = "loading"
        self._load_thread = threading.Thread(target=_run, daemon=True)
        self._load_thread.start()

    def handle_input(self, event: pygame.event.Event):
        _ = event

    def handle_action(self, action: str):
        if action == "LONG_PRESS":
            if self._expanded:
                with self._lock:
                    self._expanded = False
                    self._detail_pages = []
                    self._detail_page = 0
                return
            if self._on_back:
                self._on_back()
            return

        with self._lock:
            if self._expanded:
                if action == "SHORT_PRESS":
                    if self._detail_page < len(self._detail_pages) - 1:
                        self._detail_page += 1
                elif action == "TRIPLE_PRESS":
                    if self._detail_page > 0:
                        self._detail_page -= 1
                return

            if not self._tasks:
                return
            if action == "SHORT_PRESS":
                self._expanded = False
                self._cursor = (self._cursor + 1) % len(self._tasks)
            elif action == "TRIPLE_PRESS":
                self._expanded = False
                self._cursor = (self._cursor - 1) % len(self._tasks)
            elif action == "DOUBLE_PRESS":
                task = self._tasks[self._cursor]
                self._expand_task(task)

    def _expand_task(self, task: dict):
        """Build paginated detail view for a task's result."""
        result = task.get("result") or task.get("error") or "No result yet"
        # Wrap to fit screen width (~28 chars at body font size)
        char_w = self._font_body.size("M")[0] if self._font_body.size("M")[0] > 0 else 8
        chars_per_line = max(20, (PHYSICAL_W - 12) // char_w)
        wrapped_lines = []
        for paragraph in result.split("\n"):
            if not paragraph.strip():
                wrapped_lines.append("")
                continue
            wrapped_lines.extend(textwrap.wrap(paragraph, width=chars_per_line))

        line_h = self._font_body.get_height() + 2
        lines_per_page = max(1, (PHYSICAL_H - STATUS_BAR_H - 24) // line_h)

        pages: list[list[str]] = []
        for i in range(0, max(1, len(wrapped_lines)), lines_per_page):
            pages.append(wrapped_lines[i:i + lines_per_page])

        self._detail_pages = pages if pages else [[""]]
        self._detail_page = 0
        self._expanded = True

    def get_action_bar(self) -> list[tuple[str, str]]:
        if self._expanded:
            return [("tap", "page"), ("hold", "back")]
        if not self._tasks:
            return [("hold", "back")]
        return [("tap", "scroll"), ("2x", "expand"), ("hold", "back")]

    def _render_skeleton(self, surface, y, count=4):
        from display.skeleton import render_skeleton
        render_skeleton(surface, y, count)

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)
        title = self._font_small.render("AGENT TASKS", False, WHITE)
        surface.blit(title, (6, (STATUS_BAR_H - title.get_height()) // 2))

        with self._lock:
            state = self._state
            tasks = list(self._tasks)
            cursor = min(self._cursor, len(tasks) - 1) if tasks else 0
            expanded = self._expanded
            detail_pages = self._detail_pages
            detail_page = self._detail_page

        if state == "loading":
            self._render_skeleton(surface, STATUS_BAR_H + 12)
            return

        if state == "empty":
            s = self._font_body.render("NO SUBTASKS", False, DIM2)
            surface.blit(s, ((PHYSICAL_W - s.get_width()) // 2, PHYSICAL_H // 2))
            return

        if expanded and detail_pages:
            self._render_detail(surface, tasks, cursor, detail_pages, detail_page)
            return

        # List view
        max_rows = max(1, (PHYSICAL_H - STATUS_BAR_H - 6) // ROW_H_MIN)
        start = min(cursor, max(0, len(tasks) - max_rows))
        y = STATUS_BAR_H + 12
        for idx, task in enumerate(tasks[start:start + max_rows]):
            actual = start + idx
            focused = actual == cursor
            if focused:
                pygame.draw.rect(surface, WHITE, pygame.Rect(0, y, PHYSICAL_W, ROW_H_MIN))
            color = BLACK if focused else WHITE

            status = task.get("status", "pending")
            icon = _STATUS_ICON.get(status, "?")
            cost = task.get("cost_usd", 0.0)
            name = str(task.get("name", ""))[:18]
            cost_str = f"${cost:.3f}" if cost else ""

            # Row: name  icon  cost
            name_surf = self._font_body.render(name, False, color)
            icon_surf = self._font_small.render(icon, False, color if focused else DIM2)
            surface.blit(name_surf, (4, y + 4))
            surface.blit(icon_surf, (PHYSICAL_W - 70, y + 6))
            if cost_str:
                cost_surf = self._font_small.render(cost_str, False, color if focused else DIM3)
                surface.blit(cost_surf, (PHYSICAL_W - 44, y + 6))
            y += ROW_H_MIN

    def _render_detail(self, surface, tasks, cursor, pages, page_idx):
        """Render expanded result view with pagination."""
        task = tasks[cursor] if cursor < len(tasks) else {}
        name = str(task.get("name", ""))[:20]
        status = task.get("status", "pending")
        icon = _STATUS_ICON.get(status, "?")

        # Header
        header = f"{name}  {icon}"
        header_surf = self._font_small.render(header, False, WHITE)
        surface.blit(header_surf, (4, STATUS_BAR_H + 2))

        # Page content
        page = pages[page_idx] if page_idx < len(pages) else []
        y = STATUS_BAR_H + 18
        line_h = self._font_body.get_height() + 2
        for line in page:
            line_surf = self._font_body.render(line, False, WHITE)
            surface.blit(line_surf, (4, y))
            y += line_h

        # Page indicator
        if len(pages) > 1:
            indicator = f"{page_idx + 1}/{len(pages)}"
            ind_surf = self._font_small.render(indicator, False, DIM3)
            surface.blit(ind_surf, (PHYSICAL_W - ind_surf.get_width() - 6, PHYSICAL_H - 14))
