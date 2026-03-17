"""BITOS Files Browser Panel — browse and select files for viewing."""
from __future__ import annotations

import threading

import pygame

from screens.base import BaseScreen
from display.tokens import BLACK, WHITE, DIM2, DIM3, HAIRLINE, PHYSICAL_W, PHYSICAL_H, STATUS_BAR_H, SAFE_INSET, ROW_H_MIN
from display.theme import merge_runtime_ui_settings, load_ui_font


class FilesBrowserPanel(BaseScreen):
    """Browse and select files for viewing."""

    def __init__(self, client, repository=None, on_back=None, on_open_file=None, ui_settings=None):
        self._client = client
        self._repository = repository
        self._on_back = on_back
        self._on_open_file = on_open_file  # callback(file_data: dict) -> opens viewer
        self._ui_settings = merge_runtime_ui_settings(ui_settings)
        self._font_body = load_ui_font("body", self._ui_settings)
        self._font_small = load_ui_font("small", self._ui_settings)
        self._lock = threading.Lock()
        self._cursor = 0
        self._state = "loading"  # loading | ready | empty | error
        self._files: list[dict] = []
        self._load_thread: threading.Thread | None = None
        self._path_stack: list[str] = []  # folder drill-down stack

    @property
    def _current_path(self) -> str:
        """Current folder path from stack."""
        return self._path_stack[-1] if self._path_stack else ""

    def on_enter(self):
        self._fetch_files()

    def _fetch_files(self):
        if self._load_thread and self._load_thread.is_alive():
            return

        current_path = self._current_path

        def _run():
            try:
                files = self._client.get_files(path=current_path)
                with self._lock:
                    self._files = files
                    self._state = "ready" if files else "empty"
                    self._cursor = 0
            except Exception:
                with self._lock:
                    self._files = []
                    self._state = "error"

        self._state = "loading"
        self._load_thread = threading.Thread(target=_run, daemon=True)
        self._load_thread.start()

    def handle_input(self, event: pygame.event.Event):
        _ = event

    def handle_action(self, action: str):
        if action == "LONG_PRESS":
            # If in subfolder, pop path and go up; else call on_back
            if self._path_stack:
                self._path_stack.pop()
                self._fetch_files()
            elif self._on_back:
                self._on_back()
            return

        with self._lock:
            if not self._files:
                return

            if action == "SHORT_PRESS":
                self._cursor = (self._cursor + 1) % len(self._files)
            elif action == "TRIPLE_PRESS":
                self._cursor = (self._cursor - 1) % len(self._files)
            elif action == "DOUBLE_PRESS":
                selected = self._files[self._cursor]
                if selected.get("type") == "dir":
                    # Drill into directory — copy path before releasing lock
                    dir_path = selected.get("path", "")
                    self._path_stack.append(dir_path)
                    # NOTE: _fetch_files() must be called outside the lock
                    # to avoid deadlock (it acquires the lock internally).
                    # We break out and call it below.
                else:
                    if self._on_open_file:
                        self._on_open_file(selected)
                    return

        # If we got here from a dir DOUBLE_PRESS, fetch the new directory
        if action == "DOUBLE_PRESS":
            self._fetch_files()

    def render(self, surface: pygame.Surface):
        surface.fill(BLACK)

        # Status bar — show current path or "FILES"
        header = self._current_path if self._path_stack else "FILES"
        # Truncate long paths to fit display
        if len(header) > 24:
            header = ".../" + header.split("/")[-1] if "/" in header else header[:24]
        title = self._font_small.render(header.upper(), False, WHITE)
        surface.blit(title, (SAFE_INSET, (STATUS_BAR_H - title.get_height()) // 2))
        pygame.draw.line(surface, HAIRLINE, (0, STATUS_BAR_H - 1), (PHYSICAL_W, STATUS_BAR_H - 1))

        with self._lock:
            state = self._state
            files = list(self._files)
            cursor = self._cursor

        if state == "loading":
            from display.skeleton import render_skeleton
            render_skeleton(surface, STATUS_BAR_H + 12)
            return

        if state == "empty":
            s = self._font_body.render("NO FILES", False, DIM2)
            surface.blit(s, ((PHYSICAL_W - s.get_width()) // 2, PHYSICAL_H // 2))
            return

        if state == "error":
            s = self._font_body.render("LOAD FAILED", False, DIM2)
            surface.blit(s, ((PHYSICAL_W - s.get_width()) // 2, PHYSICAL_H // 2))
            return

        # File list
        hint_h = 14
        available_h = PHYSICAL_H - STATUS_BAR_H - SAFE_INSET - hint_h
        max_rows = max(1, available_h // ROW_H_MIN)
        start = min(cursor, max(0, len(files) - max_rows))
        y = STATUS_BAR_H + 4

        for idx, file_data in enumerate(files[start:start + max_rows]):
            actual = start + idx
            focused = actual == cursor

            if focused:
                pygame.draw.rect(surface, WHITE, pygame.Rect(0, y, PHYSICAL_W, ROW_H_MIN))

            text_color = BLACK if focused else WHITE
            dim_color = BLACK if focused else DIM3
            indicator = "> " if focused else "  "

            entry_type = file_data.get("type", "text")

            if entry_type == "dir":
                # Directory entry: show folder icon and item count
                type_label = "DIR"
                type_surf = self._font_small.render(indicator + type_label, False, dim_color)
                surface.blit(type_surf, (SAFE_INSET, y + 2))

                name = str(file_data.get("name", "untitled"))[:24]
                name_surf = self._font_body.render(name, False, text_color)
                surface.blit(name_surf, (SAFE_INSET, y + self._font_small.get_height() + 4))

                # Item count on right side
                count = file_data.get("item_count", 0)
                count_label = f"{count} items" if count != 1 else "1 item"
                count_surf = self._font_small.render(count_label, False, dim_color)
                surface.blit(count_surf, (PHYSICAL_W - SAFE_INSET - count_surf.get_width(), y + 2))
            else:
                # File entry: show type and name
                type_label = entry_type[:3].upper()
                type_surf = self._font_small.render(indicator + type_label, False, dim_color)
                surface.blit(type_surf, (SAFE_INSET, y + 2))

                name = str(file_data.get("name", "untitled"))[:24]
                name_surf = self._font_body.render(name, False, text_color)
                surface.blit(name_surf, (SAFE_INSET, y + self._font_small.get_height() + 4))

            y += ROW_H_MIN

        # Hint bar
        hint_y = PHYSICAL_H - SAFE_INSET - hint_h
        hint_center_y = hint_y + hint_h // 2
        self._render_hint_line(surface, hint_center_y)

    def _render_hint_line(self, surface: pygame.Surface, center_y: int):
        """Render compact gesture hint: tap=next  dbl=open  triple=prev  hold=back."""
        from display.tokens import DIM1
        items = [("tap", "next"), ("double", "open"), ("triple", "prev"), ("hold", "back")]
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
